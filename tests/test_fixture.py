"""Cross-implementation verification: the standalone verifier (no corrlog
imports) must agree with the corrlog SDK on frozen deterministic vectors.

This is the "trust me, here's the verification" gate: the SDK signs the
vectors; the standalone verifier — which shares zero code with the SDK —
reimplements RFC 8785 canonicalization + Ed25519 verify from the spec and
must reach the same PASS/FAIL result. If the SDK ever produces a bad
signature, this test fails.

Run: python3 tests/test_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from verifier import standalone  # noqa: E402  (the INDEPENDENT verifier)
from corrlog_core import verify, verify_chain  # noqa: E402  (the SDK)

VECTORS = REPO_ROOT / "verifier" / "vectors"


def _load(name: str) -> dict:
    return json.loads((VECTORS / name).read_text(encoding="utf-8"))


def test_sdk_and_standalone_agree_on_action():
    action = _load("action.json")
    # SDK verifies it.
    assert verify(action) is True
    # Standalone verifies it (self-auth).
    ok, reason = standalone.verify_record(action)
    assert ok is True, reason


def test_sdk_and_standalone_agree_on_chain():
    action = _load("action.json")
    correction = _load("correction.json")
    assert verify_chain([action, correction]) is True
    ok, reason = standalone.verify_chain([action, correction])
    assert ok is True, reason


def test_standalone_rejects_tampered_record():
    tampered = _load("tampered.json")
    ok, reason = standalone.verify_record(tampered)
    assert ok is False, "tampered record must fail standalone verification"


def test_standalone_rejects_wrong_key_when_pinned():
    key = _load("key.json")
    wrong = _load("wrong_key.json")
    from cryptography.hazmat.primitives.asymmetric import ed25519
    import base64
    b64 = key["publicKey"]
    pub = ed25519.Ed25519PublicKey.from_public_bytes(
        base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
    )
    ok, reason = standalone.verify_record(wrong, pinned_pub=pub)
    assert ok is False, "wrong-key record must fail when pinned to the real key"


def test_vectors_are_deterministic():
    """Re-generating must be byte-identical (frozen vectors don't drift)."""
    import subprocess
    before = {p.name: p.read_bytes() for p in VECTORS.glob("*.json")}
    gen = subprocess.run(
        [sys.executable, "verifier/generate_vectors.py"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert gen.returncode == 0, gen.stderr
    assert before == {p.name: p.read_bytes() for p in VECTORS.glob("*.json")}
    # After regeneration the action vector must be unchanged.
    # (Deterministic because the seed is fixed; this guards accidental
    #  non-determinism creeping into the signer.)
    action = _load("action.json")
    assert action["correctionId"] == "00000000-0000-4000-8000-000000000001"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} fixture tests passed.")
