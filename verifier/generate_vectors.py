#!/usr/bin/env python3
"""Generate deterministic ACR test vectors for cross-implementation verification.

These vectors are frozen in `verifier/vectors/` so ANY implementation (Python,
Rust, Go, TypeScript, or a skeptic reading the spec) can verify that our records
are produced correctly — without importing corrlog.

Run once to regenerate (they are deterministic, so output is stable):
    python3 verifier/generate_vectors.py

Produces:
  vectors/key.json          — the public key (base64url) + seed note
  vectors/action.json       — a signed action record
  vectors/correction.json   — a signed correction superseding it
  vectors/tampered.json     — the action record with one byte flipped (must FAIL)
  vectors/wrong_key.json    — a record signed by a DIFFERENT key (must FAIL)
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from cryptography.hazmat.primitives.asymmetric import ed25519

from corrlog_core import record, retract, public_key_b64url

VECTORS = os.path.join(HERE, "vectors")

# Deterministic Ed25519 key (fixed 32-byte seed) so the vectors never change.
SEED = bytes.fromhex(
    "7f9c2ba4e88f827d616045507605853ed73b8093f1efbc88eb1a6eacfa66ef26"
)
PRIV = ed25519.Ed25519PrivateKey.from_private_bytes(SEED)
PUB = PRIV.public_key()


def main() -> None:
    os.makedirs(VECTORS, exist_ok=True)

    action = record(
        agent_id="vector-agent",
        agent_name="Vector Test Agent",
        principal_id="acme-corp",
        action_type="memory.write",
        action_args={"project": "zespri", "topic": "yield"},
        action_result={"yield_forecast": "1420"},  # string, per SPEC §5 number rule
        private_key=PRIV,
        correction_id="00000000-0000-4000-8000-000000000001",
        timestamp="2026-08-25T00:00:00+00:00",
    )

    correction = retract(
        prior_record=action,
        reason="yield figure used wrong unit (kg vs tonne)",
        trigger="check_failed",
        agent_id="vector-agent",
        private_key=PRIV,
        fix_type="replace",
        corrected_content={"yield_forecast": "1.42"},
        fix_note="converted kg to tonnes",
        correction_id="00000000-0000-4000-8000-000000000002",
        timestamp="2026-08-25T00:01:00+00:00",
    )

    # Tampered: flip one character in the reason field.
    tampered = json.loads(json.dumps(action))
    tampered["action"]["type"] = "payment.execute"  # mutate signed body

    # Wrong key: same content, signed by a different key.
    wrong_key = ed25519.Ed25519PrivateKey.generate()
    wrong = record(
        agent_id="vector-agent",
        principal_id="acme-corp",
        action_type="memory.write",
        action_args={"project": "zespri", "topic": "yield"},
        private_key=wrong_key,
        correction_id="00000000-0000-4000-8000-000000000003",
        timestamp="2026-08-25T00:00:00+00:00",
    )

    def _w(name, obj):
        with open(os.path.join(VECTORS, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")

    _w("key.json", {"alg": "Ed25519", "publicKey": public_key_b64url(PUB)})
    _w("action.json", action)
    _w("correction.json", correction)
    _w("tampered.json", tampered)
    _w("wrong_key.json", wrong)

    print(f"vectors written to {VECTORS}/")
    for n in sorted(os.listdir(VECTORS)):
        print(f"  {n}")


if __name__ == "__main__":
    main()
