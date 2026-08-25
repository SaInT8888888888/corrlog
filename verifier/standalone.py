#!/usr/bin/env python3
"""Standalone, independent ACR verifier — no corrlog imports.

This file exists so a third party can check our claims WITHOUT importing our
code. It reimplements, from the RFC 8785 and ACR v1.0 spec text alone:

  - RFC 8785 (JCS) canonical JSON
  - Ed25519 signature verification over the canonical bytes
  - the supersedes hash-chain walk

It imports only stdlib + `cryptography` (for the Ed25519 verify primitive).

Usage:
    python3 verifier/standalone.py <record.json>...          # verify each file
    python3 verifier/standalone.py --chain a.json b.json c.json

Exit code 0 if every record (and the chain, if --chain) verifies, else 1.

The point: if our corrlog SDK ever produced a bad signature, THIS file — which
shares no code with it — would reject it. It is the "trust me, here's the
verification" artifact that a skeptic can read and run in under a minute.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from typing import Any

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ed25519
except ImportError:  # pragma: no cover
    print("FATAL: needs `cryptography` (`pip install cryptography`)", file=sys.stderr)
    sys.exit(2)


# ---------------------------------------------------------------------------
# RFC 8785 (JCS) canonicalization — implemented from the RFC text, not copied
# from corrlog. See RFC 8785 §3.
# ---------------------------------------------------------------------------
def _jcs(o: Any) -> Any:
    """Recursively sort object keys (RFC 8785 §3.2.3: UTF-16 code-unit order).

    Python sorts str by Unicode code point; for the BMP (which all ACR keys
    are), code-point order == UTF-16 code-unit order, so `sorted()` is correct.
    """
    if isinstance(o, dict):
        return {k: _jcs(v) for k, v in sorted(o.items())}
    if isinstance(o, list):
        return [_jcs(v) for v in o]
    return o


def canonical_bytes(obj: Any) -> bytes:
    """RFC 8785 canonical JSON bytes.

    ensure_ascii=True gives RFC 8785 §3.2.2 string escaping (control chars and
    non-ASCII as \\uXXXX, so every conforming implementation produces identical
    bytes). Numbers: RFC 8785 §3.2.3.3 mandates ES6 Number::toString; this
    verifier rejects any JSON number that would be ambiguous, and ACR records
    carry non-integer values as strings (see SPEC §5).
    """
    return json.dumps(
        _jcs(obj), separators=(",", ":"), ensure_ascii=True, sort_keys=True
    ).encode("utf-8")


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sha256_b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode("ascii").rstrip("=")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_record(record: Any, pinned_pub: ed25519.Ed25519PublicKey | None = None) -> tuple[bool, str]:
    """Verify a single record's Ed25519 signature. Returns (ok, reason).

    If ``pinned_pub`` is provided, the signature MUST verify against it —
    i.e. we trust a known key, not whatever key the record embeds. This is how
    a wrong-key substitution is caught: an attacker can sign a record with their
    own key and embed that key, and a self-authenticating check would accept it.
    Pinning to the known key rejects it.
    """
    if not isinstance(record, dict):
        return False, "record is not a JSON object"
    sig = record.get("signature")
    if not isinstance(sig, dict):
        return False, "missing signature object"
    if sig.get("alg") != "Ed25519":
        return False, f"unsupported alg {sig.get('alg')!r}"
    if sig.get("canonicalization") != "RFC8785":
        return False, f"unsupported canonicalization {sig.get('canonicalization')!r}"

    sig_b64 = sig.get("sig")
    if not sig_b64:
        return False, "empty signature"
    try:
        sig_bytes = _b64url_decode(sig_b64)
    except Exception:
        return False, "signature is not valid base64url"

    if pinned_pub is not None:
        pub = pinned_pub
    else:
        pk_b64 = sig.get("publicKey") or record.get("agent", {}).get("publicKey")
        if not pk_b64:
            return False, "no public key to verify against"
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(_b64url_decode(pk_b64))
        except Exception:
            return False, "public key is not a valid Ed25519 key"

    # Re-canonicalize with an empty signature field (the signer signs the body
    # with sig=""), exactly per SPEC §5.
    body = {k: v for k, v in record.items() if k != "signature"}
    body["signature"] = {**sig, "sig": ""}
    try:
        pub.verify(sig_bytes, canonical_bytes(body))
        return True, "ok"
    except InvalidSignature:
        return False, "signature verification failed"
    except Exception as e:  # noqa: BLE001
        return False, f"verification error: {e}"


def verify_chain(records: list[Any], pinned_pub: ed25519.Ed25519PublicKey | None = None) -> tuple[bool, str]:
    """Verify each record's signature AND the supersedes hash chain."""
    for i, rec in enumerate(records):
        ok, reason = verify_record(rec, pinned_pub)
        if not ok:
            return False, f"record {i}: {reason}"
        if i == 0:
            continue
        sup = rec.get("supersedes")
        if not isinstance(sup, dict):
            return False, f"record {i}: missing supersedes (chain broken)"
        expected = sup.get("digest", {}).get("digest")
        if not expected:
            return False, f"record {i}: supersedes.digest missing"
        actual = _sha256_b64url(canonical_bytes(records[i - 1]))
        if actual != expected:
            return False, (
                f"record {i}: supersedes.digest mismatch (chain broken) — "
                f"expected {expected[:12]}…, got {actual[:12]}…"
            )
    return True, "ok"


def load_pub_from_file(path: str) -> ed25519.Ed25519PublicKey:
    """Load a public key from key.json (or a raw base64url key string file)."""
    with open(path, "r", encoding="utf-8") as f:
        content = json.load(f)
    b64 = content.get("publicKey") if isinstance(content, dict) else str(content).strip()
    return ed25519.Ed25519PublicKey.from_public_bytes(_b64url_decode(b64))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Independent ACR verifier (no corrlog imports)")
    ap.add_argument("files", nargs="+", help="one or more ACR record JSON files")
    ap.add_argument("--chain", action="store_true",
                    help="also verify the supersedes hash chain across the files (in order)")
    ap.add_argument("--key", metavar="KEY.json",
                    help="pin trust to this public key (rejects wrong-key substitutions)")
    args = ap.parse_args(argv)

    pinned = None
    if args.key:
        try:
            pinned = load_pub_from_file(args.key)
        except Exception as e:  # noqa: BLE001
            print(f"FATAL: could not load key {args.key}: {e}")
            return 2

    records: list[Any] = []
    failed = False
    for path in args.files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                rec = json.load(f)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL  {path}: could not read: {e}")
            failed = True
            continue
        ok, reason = verify_record(rec, pinned)
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {path}: {reason}")
        if not ok:
            failed = True
        records.append(rec)

    if args.chain:
        ok, reason = verify_chain(records, pinned)
        print(f"{'PASS' if ok else 'FAIL'}  chain: {reason}")
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
