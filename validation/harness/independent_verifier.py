#!/usr/bin/env python3
"""INDEPENDENT ACR/CorrLog verifier — shares NO code with corrlog.

Deliberate contrast with corrlog-sdk/verifier/standalone.py:

  * standalone.py reimplements canonicalization by hand and makes the SAME
    choice corrlog-core makes (`ensure_ascii=True`), so it cannot detect a
    canonicalization divergence. It is independent of corrlog's *code* but not
    of its *assumptions*.
  * This verifier delegates canonicalization to a third-party RFC 8785
    implementation (`rfc8785`, Trail of Bits) that was written independently of
    corrlog. It is therefore an oracle for the spec, not a re-statement of the
    implementation.

It uses only: stdlib + `cryptography` (Ed25519 primitive) + `rfc8785`.

Usage:
    independent_verifier.py --key key.json record.json [record2.json ...]
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def canonical_bytes(obj) -> bytes:
    """RFC 8785 JCS via the independent third-party implementation."""
    return rfc8785.dumps(obj)


def verify_record(record, pinned_pub=None):
    """Return (ok, reason). Mirrors the ACR spec's verification procedure."""
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

    body = {k: v for k, v in record.items() if k != "signature"}
    body["signature"] = {**sig, "sig": ""}
    try:
        pub.verify(sig_bytes, canonical_bytes(body))
        return True, "ok"
    except InvalidSignature:
        return False, "signature verification failed"
    except Exception as e:
        return False, f"canonicalization/verification error: {type(e).__name__}: {e}"


def verify_chain(records, pinned_pub=None):
    """Verify signatures AND the supersedes hash chain, strictly.

    Stricter than corrlog's own verify_chain: the FIRST record must not carry a
    supersedes pointer (a chain presented for verification must be rooted), so a
    truncated chain is rejected rather than silently accepted.
    """
    for i, rec in enumerate(records):
        ok, reason = verify_record(rec, pinned_pub)
        if not ok:
            return False, f"record {i}: {reason}"
        if i == 0:
            if isinstance(rec, dict) and rec.get("supersedes"):
                return False, ("record 0: carries a supersedes pointer but no predecessor "
                               "was presented (truncated chain)")
            continue
        sup = rec.get("supersedes")
        if not isinstance(sup, dict):
            return False, f"record {i}: missing supersedes (chain broken)"
        expected = sup.get("digest", {}).get("digest")
        if not expected:
            return False, f"record {i}: supersedes.digest missing"
        actual = _b64url(hashlib.sha256(canonical_bytes(records[i - 1])).digest())
        if actual != expected:
            return False, f"record {i}: supersedes.digest mismatch (chain broken)"
    return True, "ok"


def load_pub(path: str) -> ed25519.Ed25519PublicKey:
    content = json.load(open(path, encoding="utf-8"))
    b64 = content.get("publicKey") if isinstance(content, dict) else str(content).strip()
    return ed25519.Ed25519PublicKey.from_public_bytes(_b64url_decode(b64))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Independent ACR verifier (oracle RFC 8785)")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--key", metavar="KEY.json")
    args = ap.parse_args(argv)

    pinned = None
    if args.key:
        try:
            pinned = load_pub(args.key)
        except Exception as e:
            print(f"FATAL: could not load key {args.key}: {e}")
            return 2

    records, failed = [], False
    for path in args.files:
        try:
            rec = json.load(open(path, encoding="utf-8"))
        except Exception as e:
            print(f"FAIL  {path}: could not read: {e}")
            failed = True
            continue
        ok, reason = verify_record(rec, pinned)
        print(f"{'PASS' if ok else 'FAIL'}  {path}: {reason}")
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
