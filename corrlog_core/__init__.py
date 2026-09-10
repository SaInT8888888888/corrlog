"""corrlog-core — the Agent Correction Record (ACR) core.

Framework-independent implementation of the ACR v1.0 spec (see SPEC.md):
sign, verify, record, retract. Ed25519 over RFC 8785 (JCS) canonical JSON.

Runtime dependencies: cryptography and jsonschema.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import uuid
import copy
from importlib.resources import files
from jsonschema import Draft202012Validator, FormatChecker
from datetime import datetime, timezone
from typing import Any, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

__version__ = "0.2.2"
from cryptography.hazmat.primitives.asymmetric import ed25519

CANONICALIZATION = "RFC8785"
VALID_TRIGGERS = ("supersede", "check_failed", "human_flagged", "self_correction")
VALID_FIX_TYPES = ("replace", "delete", "rollback", "noop", "other")
VALID_SOURCE_TYPES = ("schema", "document", "database", "api", "human", "other")


# ---------------------------------------------------------------------------
# Canonical JSON per RFC 8785 (JCS — JSON Canonicalization Scheme)
# ---------------------------------------------------------------------------
_JCS_ESCAPES = {
    0x08: "\\b", 0x09: "\\t", 0x0A: "\\n", 0x0C: "\\f", 0x0D: "\\r",
    0x22: '\\"', 0x5C: "\\\\",
}


def _jcs_escape_string(s: str) -> str:
    """RFC 8785 §3.2.2.2 string serialization.

    Only '"', '\\', and U+0000–U+001F are escaped; everything else is emitted
    as-is (raw UTF-8 in the output). A lone surrogate is an error, as the RFC
    requires. (The previous implementation used ``ensure_ascii=True``, which
    escaped every non-ASCII character as ``\\uXXXX``; that is *not* JCS and
    produces canonical bytes no conforming implementation reproduces.)
    """
    out = ['"']
    for ch in s:
        o = ord(ch)
        if o in _JCS_ESCAPES:
            out.append(_JCS_ESCAPES[o])
        elif o < 0x20:
            out.append("\\u%04x" % o)
        elif 0xD800 <= o <= 0xDFFF:
            raise ValueError(
                "cannot canonicalize a lone surrogate; RFC 8785 3.2.2.2 "
                "requires a compliant implementation to terminate with an error"
            )
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _jcs_number(value: Any) -> str:
    """RFC 8785 §3.2.2.3 number serialization (ES6 ``Number::toString``).

    Differs from Python's ``repr`` in ways that matter for interoperability:
    56.0 renders as ``56``, 1e16 as ``10000000000000000`` (not ``1e+16``) and
    1e-7 as ``1e-7`` (not ``1e-07``).
    """
    if isinstance(value, bool):  # bool is an int subclass; never a JSON number
        raise TypeError("bool is not a JSON number")
    if isinstance(value, int):
        if abs(value) < 2 ** 53:  # exactly representable as a double
            return str(value)
        raise ValueError("integers outside the safe IEEE 754 range must be strings")
    x = float(value)
    if math.isnan(x) or math.isinf(x):
        raise ValueError("Out of range IEEE 754 number cannot be serialized")
    if x == 0.0:
        return "0"

    r = repr(x)
    neg = r.startswith("-")
    if neg:
        r = r[1:]
    if "e" in r:
        mant, _, exp = r.partition("e")
        exp = int(exp)
        digits = mant.replace(".", "")
        n = (mant.index(".") if "." in mant else len(mant)) + exp
    elif "." in r:
        int_part, frac = r.split(".")
        digits = int_part + frac
        n = len(int_part)
    else:
        digits, n = r, len(r)

    lead = len(digits) - len(digits.lstrip("0"))
    digits = digits.lstrip("0") or "0"
    n -= lead
    digits = digits.rstrip("0") or "0"
    k = len(digits)

    if k <= n <= 21:
        s = digits + "0" * (n - k)
    elif 0 < n <= 21:
        s = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        s = "0." + "0" * (-n) + digits
    elif k == 1:
        s = digits + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    else:
        s = digits[0] + "." + digits[1:] + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    return ("-" if neg else "") + s


def _jcs_render(obj: Any, out: list[str]) -> None:
    if obj is None:
        out.append("null")
    elif obj is True:
        out.append("true")
    elif obj is False:
        out.append("false")
    elif isinstance(obj, str):
        out.append(_jcs_escape_string(obj))
    elif isinstance(obj, (int, float)):
        out.append(_jcs_number(obj))
    elif isinstance(obj, dict):
        out.append("{")
        for i, key in enumerate(sorted(obj, key=_jcs_sort_key)):
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            if i:
                out.append(",")
            out.append(_jcs_escape_string(key))
            out.append(":")
            _jcs_render(obj[key], out)
        out.append("}")
    elif isinstance(obj, (list, tuple)):
        out.append("[")
        for i, item in enumerate(obj):
            if i:
                out.append(",")
            _jcs_render(item, out)
        out.append("]")
    else:
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _jcs_sort_key(key: str) -> bytes:
    """RFC 8785 §3.2.3: sort object keys by UTF-16 code units.

    Python's default ``sorted()`` compares by Unicode code point, which orders
    astral-plane keys differently from UTF-16 and so diverges from JCS on any
    object with a non-BMP key.
    """
    return key.encode("utf-16-be", "surrogatepass")


def canonical_json(obj: dict[str, Any]) -> bytes:
    """Return RFC 8785 (JCS) canonical bytes.

    Recursive key sort by UTF-16 code unit order, RFC 8785 string escaping
    (non-ASCII emitted raw, not ``\\uXXXX``), ES6 number serialization, no
    insignificant whitespace, UTF-8 output. Validated against all six official
    JCS conformance vectors (cyberphone/json-canonicalization) and byte-compared
    against an independent implementation (``rfc8785``) over randomized inputs.
    """
    out: list[str] = []
    _jcs_render(obj, out)
    return "".join(out).encode("utf-8")


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
        # allow a small prefix for readability; strip it. (The previous version
        # stripped only 2 characters for "sk_", which corrupted the seed and made
        # the documented sk_ prefix unusable.)
        if s.startswith("ed25519:"):
            s = s.split(":", 1)[1]
        elif s.startswith("priv_"):
            s = s[5:]
        else:
            s = s[3:]
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
        "metadata": copy.deepcopy(metadata) if metadata is not None else {},
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
    validate_record(body)
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
    source_type: str | None = None,
    source_reference: str | None = None,
    kid: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a signed correction record that supersedes `prior_record`.

    `prior_record` is the action record (or prior correction) being amended.
    The supersedes pointer is a SHA-256 content hash of the prior record's
    canonical bytes - not just an id - so the chain is verifiable offline.

    `source_type` + `source_reference` record WHERE the correct value came from
    (schema, document, database, api, human, other). These are signed assertions;
    consumers must independently check the reference and its correctness.

    ``correction_id`` and ``timestamp`` are OPTIONAL and exist for deterministic
    test vectors (reproducible records, cross-implementation verification).
    """
    if trigger not in VALID_TRIGGERS:
        raise ValueError(f"trigger must be one of {VALID_TRIGGERS}, got {trigger!r}")
    if fix_type not in VALID_FIX_TYPES:
        raise ValueError(f"fix.type must be one of {VALID_FIX_TYPES}, got {fix_type!r}")
    if source_type is not None and source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"source.type must be one of {VALID_SOURCE_TYPES}, got {source_type!r}")
    if (source_type is None) != (source_reference is None):
        raise ValueError("source_type and source_reference must be provided together")

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
        "metadata": copy.deepcopy(metadata) if metadata is not None else {},
    }
    if fix_note:
        body["fix"]["note"] = fix_note
    if corrected_content is not None:
        body["fix"]["contentHash"] = _hash_object(
            canonical_json(corrected_content)
            if isinstance(corrected_content, dict)
            else str(corrected_content).encode()
        )
    if source_type is not None:
        body["fix"]["source"] = {"type": source_type, "reference": source_reference}

    _sign(body, private_key, kid)
    validate_record(body)
    return body


def unknown(
    *,
    agent_id: str,
    private_key: ed25519.Ed25519PrivateKey,
    subject: str,
    note: str | None = None,
    agent_name: str | None = None,
    principal_id: str = "unknown",
    principal_type: str = "organization",
    kid: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Build a signed "I don't know" (uncertainty) record.

    This is the honesty record: an agent records that it does NOT know
    something, instead of guessing and later needing a correction. It has no
    ``supersedes`` pointer (nothing is being corrected) and no ``fix`` - it is
    a first-class declaration of uncertainty, signed so it is attributable.

    This is what turns "the agent said so when it didn't know" from a
    behaviour you have to trust into a record you can verify. The complement
    to ``retract``: retract records a mistake AFTER it was caught; ``unknown``
    records the uncertainty BEFORE a mistake could be made.

    ``correction_id`` and ``timestamp`` are OPTIONAL for deterministic test
    vectors. The record reuses the ``correctionId`` key for chain-linking
    consistency even though it is not itself a correction.
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
        "kind": "unknown",
        "subject": subject,
        "note": note or "",
        "timestamp": ts,
        "metadata": copy.deepcopy(metadata) if metadata is not None else {},
    }
    if agent_name:
        body["agent"]["name"] = agent_name

    _sign(body, private_key, kid)
    validate_record(body)
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
    is used for signature consistency ONLY, not signer trust. Prefer verify_trusted
    with an independently established key for security decisions.
    """
    if not isinstance(record, dict):
        return False
    try:
        validate_record(record)
        sig_meta = record["signature"]
        embedded = load_public_key(sig_meta["publicKey"])
        if record["agent"].get("publicKey", sig_meta["publicKey"]) != sig_meta["publicKey"]:
            return False
        if public_key is not None and public_key_b64url(public_key) != public_key_b64url(embedded):
            return False
        key = public_key if public_key is not None else embedded
        sig_bytes = _decode_exact(sig_meta["sig"], 64)
        payload = {**record, "signature": {**sig_meta, "sig": ""}}
        key.verify(sig_bytes, canonical_json(payload))
        return True
    except Exception:
        return False


def _decode_exact(value: str, size: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError("expected unpadded base64url string")
    raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    if len(raw) != size or _b64url(raw) != value:
        raise ValueError("invalid length or noncanonical base64url")
    return raw


def load_public_key(value: str) -> ed25519.Ed25519PublicKey:
    """Decode an independently provisioned, unpadded base64url public key.

    Decoding is not trust establishment. Obtain this value through an authenticated
    channel and bind it to the expected signer before inspecting received records.
    """
    return ed25519.Ed25519PublicKey.from_public_bytes(_decode_exact(value, 32))


def verify_trusted(record: Any, public_key: ed25519.Ed25519PublicKey) -> bool:
    """Fail closed without an explicitly supplied trusted Ed25519 public key."""
    return isinstance(public_key, ed25519.Ed25519PublicKey) and verify(record, public_key)


_SCHEMA = json.loads(files("corrlog_core").joinpath("schema/acr-v1.json").read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA, format_checker=FormatChecker())


def validate_record(record: Any) -> None:
    """Raise ValueError for invalid record structure, formats, or JSON values."""
    try:
        _VALIDATOR.validate(record)
        canonical_json(record)
    except Exception as exc:
        raise ValueError("invalid ACR record") from exc


def chain_checkpoint(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe a chain; NOT a trust-establishment or signing operation.

    A trusted producer must distribute and retain this checkpoint separately.
    A checkpoint received alongside an untrusted chain establishes nothing.
    """
    if not verify_chain(records):
        raise ValueError("invalid correction chain")
    return {"length": len(records), "genesis": _hash_object(canonical_json(records[0]))["digest"],
            "head": _hash_object(canonical_json(records[-1]))["digest"]}


def verify_chain(records: list[dict[str, Any]], public_key: ed25519.Ed25519PublicKey | None = None,
                 *, checkpoint: dict[str, Any] | None = None) -> bool:
    """Check a rooted linear correction chain, including unique IDs and links.

    Without a separately trusted checkpoint, a valid prefix is accepted: this
    proves link consistency, not complete history or JSONL file integrity.
    A checkpoint requires a trusted key and binds length, genesis and head.
    """
    try:
        if not isinstance(records, list) or not records:
            return False
        seen = set()
        for i, rec in enumerate(records):
            if not verify(rec, public_key) or rec["correctionId"] in seen:
                return False
            seen.add(rec["correctionId"])
            if i == 0:
                if "supersedes" in rec:
                    return False
            else:
                sup = rec.get("supersedes", {})
                if sup.get("receiptId") != records[i-1]["correctionId"]:
                    return False
                if sup.get("digest") != _hash_object(canonical_json(records[i-1])):
                    return False
        if checkpoint is not None:
            if not isinstance(public_key, ed25519.Ed25519PublicKey):
                return False
            if not isinstance(checkpoint, dict) or type(checkpoint.get("length")) is not int:
                return False
            expected = {"length": len(records),
                        "genesis": _hash_object(canonical_json(records[0]))["digest"],
                        "head": _hash_object(canonical_json(records[-1]))["digest"]}
            if checkpoint != expected:
                return False
        return True
    except Exception:
        return False


def tamper_evident(record: dict[str, Any]) -> bool:
    """Compatibility signature-consistency check; does not establish signer trust."""
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
        if any(r.get("correctionId") == record.get("correctionId") for r in self._records):
            raise ValueError("duplicate correctionId")
        self._records.append(copy.deepcopy(record))

    def get(self, correction_id: str) -> dict[str, Any] | None:
        for r in self._records:
            if r.get("correctionId") == correction_id:
                return copy.deepcopy(r)
        return None

    def all(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._records)


class JsonlSink:
    """JSONL transport sink. No ledger integrity, uniqueness or replay guarantee.

    Durability contract (exact, no stronger claim):
      * each ``append`` submits one complete JSON line to an O_APPEND file;
        concurrent append behavior depends on the filesystem and platform.
        This is not an integrity, exactly-once or universal atomicity guarantee;
      * there is NO fsync: a process crash (SIGKILL, power loss) can lose the
        most recent writes still in the page cache, and a write killed
        mid-record can leave a PARTIAL trailing line;
      * ``append`` first closes any unterminated trailing line left by a
        crashed writer, so a new record is never glued onto a damaged tail;
      * readers tolerate damage: ``all()`` skips unparseable lines instead of
        raising, and reports how many were skipped via ``damaged_lines``.
        A damaged trailing line therefore never makes earlier history
        unreadable, and appends can safely continue afterwards.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        # Number of unparseable lines skipped by the most recent all() call.
        self.damaged_lines = 0

    def append(self, record: dict[str, Any]) -> None:
        # ensure_ascii=True so lone surrogates in content are escaped to
        # \uXXXX and can never raise UnicodeEncodeError or corrupt the line
        # Storage escaping is separate from RFC 8785 signing canonicalization.
        # Binary mode: the record is encoded first and written as one
        # contiguous block, so on POSIX O_APPEND files each append stays
        # atomic against other concurrent appenders.
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n"
        with open(self.path, "ab+") as f:
            # If a crashed writer left an unterminated trailing line, close it
            # first so this record starts on its own line.
            try:
                f.seek(-1, 2)
                if f.read(1) != b"\n":
                    f.write(b"\n")
            except OSError:
                pass  # empty file or seek unsupported; write the record as-is
            f.write(line)

    def get(self, correction_id: str) -> dict[str, Any] | None:
        for r in self.all():
            if r.get("correctionId") == correction_id:
                return copy.deepcopy(r)
        return None

    def all(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        damaged = 0
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        # A crashed writer can leave a partial trailing line.
                        # Skip it: earlier history stays readable and usable.
                        damaged += 1
        except FileNotFoundError:
            pass
        self.damaged_lines = damaged
        return out
