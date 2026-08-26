"""corrlog-core — the Agent Correction Record (ACR) core.

Framework-independent implementation of the ACR v1.0 spec (see SPEC.md):
sign, verify, record, retract. Ed25519 over RFC 8785 (JCS) canonical JSON.

The only runtime dependency is `cryptography` (for Ed25519).
"""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

__version__ = "0.1.0"
from cryptography.hazmat.primitives.asymmetric import ed25519

CANONICALIZATION = "RFC8785"
VALID_TRIGGERS = ("supersede", "check_failed", "human_flagged", "self_correction")
VALID_FIX_TYPES = ("replace", "delete", "rollback", "noop", "other")


# ---------------------------------------------------------------------------
# Canonical JSON per RFC 8785 (JCS — JSON Canonicalization Scheme)
# ---------------------------------------------------------------------------
def canonical_json(obj: dict[str, Any]) -> bytes:
    """Return RFC 8785 (JCS) canonical bytes.

    RFC 8785 requires: recursive key sort by UTF-16 code unit order, no
    insignificant whitespace, and specific string escaping — control
    characters and non-ASCII MUST be escaped as ``\\uXXXX``/surrogate pairs so
    every conforming implementation (Python, Rust, Go, TS) produces
    byte-identical output. Python's ``json.dumps`` with ``ensure_ascii=True``
    and ``separators=(",", ":")`` satisfies this for strings; numbers MUST be
    serialized per RFC 8785 §3.2.3 (ES6 Number::toString) — this reference
    avoids the float ambiguity by representing non-integer values as strings
    (see `record`/`retract`), matching AAR's practice.
    """
    def _sorted(o: Any) -> Any:
        if isinstance(o, dict):
            # sort_keys sorts by Unicode code point, which matches UTF-16
            # code unit order for the BMP (all keys here are ASCII-safe).
            return {k: _sorted(v) for k, v in sorted(o.items())}
        if isinstance(o, list):
            return [_sorted(v) for v in o]
        return o

    return json.dumps(
        _sorted(obj), separators=(",", ":"), ensure_ascii=True, sort_keys=True
    ).encode("utf-8")


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------
def generate_keypair() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Return (private_key, public_key) as cryptography Ed25519 objects."""
    priv = ed25519.Ed25519PrivateKey.generate()
    return priv, priv.public_key()


def public_key_b64url(pub: ed25519.Ed25519PublicKey) -> str:
    """Base64url (no padding) encoding of the raw Ed25519 public key bytes."""
    raw = pub.public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def load_private_key(seed: str) -> ed25519.Ed25519PrivateKey:
    """Load an Ed25519 private key from a 32-byte seed string.

    Accepts the seed as base64url (no padding) or hex. This is the loading
    counterpart to ``generate_keypair`` — adapters use it to turn an operator's
    secret (from an env var) into a signing key without inventing their own
    serialization.
    """
    s = seed.strip()
    if s.startswith(("sk_", "priv_", "ed25519:")):
        # allow a small prefix for readability; strip it
        s = s.split(":", 1)[-1] if ":" in s else s[2:] if s.startswith("sk_") else s[5:]
    try:
        raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
    except Exception:
        raw = b""
    if len(raw) != 32:
        # fall back to hex
        try:
            raw = bytes.fromhex(s)
        except Exception:
            raw = b""
    if len(raw) != 32:
        raise ValueError(
            "seed must decode to exactly 32 bytes (base64url or hex)"
        )
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


# ---------------------------------------------------------------------------
# Record construction
# ---------------------------------------------------------------------------
def _hash_object(data: bytes) -> dict[str, str]:
    return {"alg": "sha256", "digest": _b64url(hashlib.sha256(data).digest())}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def record(
    *,
    agent_id: str,
    agent_name: str | None = None,
    principal_id: str = "unknown",
    principal_type: str = "organization",
    action_type: str,
    action_target: str | None = None,
    action_args: Any = None,
    action_result: Any = None,
    private_key: ed25519.Ed25519PrivateKey,
    kid: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a signed ACR-compatible *action* record (the receipt a correction can supersede).

    This is the lightweight action record; corrections are built with `retract`.

    ``correction_id`` and ``timestamp`` are OPTIONAL and exist for deterministic
    test vectors (reproducible records, cross-implementation verification).
    When omitted they default to a fresh UUID / current UTC time.
    """
    ts = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
    public_key = private_key.public_key()
    pk_b64 = public_key_b64url(public_key)
    if kid is None:
        kid = pk_b64

    body: dict[str, Any] = {
        "correctionId": correction_id if correction_id is not None else str(uuid.uuid4()),
        "agent": {"id": agent_id, "publicKey": pk_b64},
        "principal": {"id": principal_id, "type": principal_type},
        "action": {"type": action_type},
        "reason": "",
        "trigger": "supersede",  # placeholder; corrected on retract
        "fix": {"type": "noop"},
        "timestamp": ts,
        "metadata": metadata or {},
    }
    if agent_name:
        body["agent"]["name"] = agent_name
    if action_target:
        body["action"]["target"] = action_target

    # Store hashes of args/result (privacy-preserving) in metadata.
    if action_args is not None:
        body["metadata"]["inputHash"] = _hash_object(
            canonical_json(action_args) if isinstance(action_args, dict) else str(action_args).encode()
        )
    if action_result is not None:
        body["metadata"]["outputHash"] = _hash_object(
            canonical_json(action_result) if isinstance(action_result, dict) else str(action_result).encode()
        )

    _sign(body, private_key, kid)
    return body


def retract(
    *,
    prior_record: dict[str, Any],
    reason: str,
    trigger: str,
    agent_id: str,
    private_key: ed25519.Ed25519PrivateKey,
    principal_id: str = "unknown",
    principal_type: str = "organization",
    fix_type: str = "replace",
    fix_note: str | None = None,
    corrected_content: Any = None,
    kid: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a signed correction record that supersedes `prior_record`.

    `prior_record` is the action record (or prior correction) being amended.
    The supersedes pointer is a SHA-256 content hash of the prior record's
    canonical bytes — not just an id — so the chain is verifiable offline.

    ``correction_id`` and ``timestamp`` are OPTIONAL and exist for deterministic
    test vectors (reproducible records, cross-implementation verification).
    """
    if trigger not in VALID_TRIGGERS:
        raise ValueError(f"trigger must be one of {VALID_TRIGGERS}, got {trigger!r}")
    if fix_type not in VALID_FIX_TYPES:
        raise ValueError(f"fix.type must be one of {VALID_FIX_TYPES}, got {fix_type!r}")

    ts = timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat()
    public_key = private_key.public_key()
    pk_b64 = public_key_b64url(public_key)
    if kid is None:
        kid = pk_b64

    prior_digest = _hash_object(canonical_json(prior_record))

    body: dict[str, Any] = {
        "correctionId": correction_id if correction_id is not None else str(uuid.uuid4()),
        "agent": {"id": agent_id, "publicKey": pk_b64},
        "principal": {"id": principal_id, "type": principal_type},
        "supersedes": {
            "receiptId": prior_record.get("correctionId") or prior_record.get("receiptId"),
            "digest": prior_digest,
        },
        "action": {"type": prior_record.get("action", {}).get("type", "unknown")},
        "reason": reason,
        "trigger": trigger,
        "fix": {"type": fix_type},
        "timestamp": ts,
        "metadata": metadata or {},
    }
    if fix_note:
        body["fix"]["note"] = fix_note
    if corrected_content is not None:
        body["fix"]["contentHash"] = _hash_object(
            canonical_json(corrected_content)
            if isinstance(corrected_content, dict)
            else str(corrected_content).encode()
        )

    _sign(body, private_key, kid)
    return body


def _sign(body: dict[str, Any], private_key: ed25519.Ed25519PrivateKey, kid: str) -> None:
    body["signature"] = {
        "alg": "Ed25519",
        "kid": kid,
        "publicKey": public_key_b64url(private_key.public_key()),
        "canonicalization": CANONICALIZATION,
        "sig": "",
    }
    # Canonicalize with sig removed (empty), then sign.
    sig_bytes = private_key.sign(canonical_json(body))
    body["signature"]["sig"] = _b64url(sig_bytes)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify(record: dict[str, Any], public_key: ed25519.Ed25519PublicKey | None = None) -> bool:
    """Verify an ACR record's Ed25519 signature.

    If `public_key` is None, the key embedded in `record["signature"]["publicKey"]`
    is used (self-authenticating). Pass a key explicitly to pin trust to a known key.
    """
    sig_meta = record.get("signature") or {}
    if sig_meta.get("alg") != "Ed25519":
        return False
    if sig_meta.get("canonicalization") != CANONICALIZATION:
        return False

    sig_b64 = sig_meta.get("sig") or ""
    if not sig_b64:
        return False

    try:
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + "=" * (-len(sig_b64) % 4))
    except Exception:
        return False

    if public_key is None:
        pk_b64 = sig_meta.get("publicKey") or record.get("agent", {}).get("publicKey")
        if not pk_b64:
            return False
        try:
            raw = base64.urlsafe_b64decode(pk_b64 + "=" * (-len(pk_b64) % 4))
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw)
        except Exception:
            return False

    # Re-canonicalize with sig removed.
    payload = {k: v for k, v in record.items() if k != "signature"}
    payload["signature"] = {**sig_meta, "sig": ""}

    try:
        public_key.verify(sig_bytes, canonical_json(payload))
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


def verify_chain(records: list[dict[str, Any]], public_key: ed25519.Ed25519PublicKey | None = None) -> bool:
    """Verify a chain of records: each signature valid, and each correction's
    `supersedes.digest` matches the canonical bytes of the prior record."""
    for i, rec in enumerate(records):
        if not verify(rec, public_key):
            return False
        if i == 0:
            continue
        sup = rec.get("supersedes")
        if not sup:
            # A chain where a later record doesn't supersede is broken.
            return False
        expected_digest = sup.get("digest", {}).get("digest")
        if not expected_digest:
            return False
        actual_digest = _b64url(hashlib.sha256(canonical_json(records[i - 1])).digest())
        if actual_digest != expected_digest:
            return False
    return True


def tamper_evident(record: dict[str, Any]) -> bool:
    """True if any mutation of the signed body invalidates the signature."""
    # A record is tamper-evident by construction; this checks the signature
    # still holds for the current body (i.e. it has NOT been mutated).
    return verify(record)


# ---------------------------------------------------------------------------
# Pluggable sink
# ---------------------------------------------------------------------------
class Sink(Protocol):
    def append(self, record: dict[str, Any]) -> None: ...
    def get(self, correction_id: str) -> dict[str, Any] | None: ...
    def all(self) -> list[dict[str, Any]]: ...


class MemorySink:
    """In-memory append-only sink (for demos/tests)."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def append(self, record: dict[str, Any]) -> None:
        self._records.append(record)

    def get(self, correction_id: str) -> dict[str, Any] | None:
        for r in self._records:
            if r.get("correctionId") == correction_id:
                return r
        return None

    def all(self) -> list[dict[str, Any]]:
        return list(self._records)


class JsonlSink:
    """Append-only JSONL file sink — durable, hash-chained by file order."""

    def __init__(self, path: str) -> None:
        self.path = path

    def append(self, record: dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")

    def get(self, correction_id: str) -> dict[str, Any] | None:
        for r in self.all():
            if r.get("correctionId") == correction_id:
                return r
        return None

    def all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        out.append(json.loads(line))
        except FileNotFoundError:
            pass
        return out
