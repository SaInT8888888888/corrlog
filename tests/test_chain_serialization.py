"""Chains and checkpoints must survive the wire form, not just in-memory objects.

A chain record carries a digest of its predecessor computed over the predecessor's
canonical bytes. If a record does not canonicalize identically after a serialise and
parse round-trip, linked records stop verifying even though nothing was tampered
with. The retest asked specifically for checkpoint chains to be checked after
serialization, which this file does.

Appendix B numeric values are included deliberately: their canonical spelling is not
the exact value of the double, so the numeric domain is exercised inside the chain
digest as well as in the signature.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from corrlog_core import (
    canonical_json,
    chain_checkpoint,
    generate_keypair,
    public_key_b64url,
    record,
    retract,
    verify_chain,
)
from verifier import standalone

VERIFIER = Path(__file__).resolve().parent.parent / "verifier" / "standalone.py"

NUMERIC_VALUES = [
    float(2 ** 68),
    float(10 ** 18 + 128),
    999999999999999700000.0,
    1e16,
    0.1,
    56.0,
]


def _chain(value):
    private, trusted = generate_keypair()
    r1 = record(agent_id="chain", action_type="post", private_key=private,
                timestamp="2026-09-10T00:00:00+00:00", metadata={"value": value})
    r2 = retract(prior_record=r1, reason="café 😀 wrong account",
                 trigger="check_failed", agent_id="chain", private_key=private,
                 timestamp="2026-09-10T00:01:00+00:00", metadata={"value": value})
    r3 = retract(prior_record=r2, reason="wrong tax code",
                 trigger="check_failed", agent_id="chain", private_key=private,
                 timestamp="2026-09-10T00:02:00+00:00", metadata={"value": value})
    return private, trusted, [r1, r2, r3]


@pytest.mark.parametrize("value", NUMERIC_VALUES)
def test_chain_and_checkpoint_survive_serialization(value):
    private, trusted, chain = _chain(value)
    assert verify_chain(chain, trusted)
    checkpoint = chain_checkpoint(chain)
    assert verify_chain(chain, trusted, checkpoint=checkpoint)

    roundtrips = {
        "canonical": lambda r: json.loads(canonical_json(r)),
        "plain": lambda r: json.loads(json.dumps(r)),
    }
    for label, rt in roundtrips.items():
        wire = [rt(r) for r in chain]
        assert verify_chain(wire, trusted), f"{label} chain failed verification"
        assert verify_chain(wire, trusted, checkpoint=checkpoint), \
            f"{label} chain failed the checkpoint check"
        ok, reason = standalone.verify_chain(wire, trusted, checkpoint=checkpoint)
        assert ok, f"{label} chain failed in the standalone verifier: {reason}"


@pytest.mark.parametrize("value", NUMERIC_VALUES)
def test_chain_tamper_still_rejected_after_serialization(value):
    """Serialization must not weaken the chain checks."""
    private, trusted, chain = _chain(value)
    wire = [json.loads(canonical_json(r)) for r in chain]
    assert verify_chain(wire, trusted)

    reordered = [wire[1], wire[0], wire[2]]
    assert not verify_chain(reordered, trusted)

    truncated = wire[:-1]
    assert verify_chain(truncated, trusted)  # valid prefix, documented behaviour
    assert not verify_chain(truncated, trusted, checkpoint=chain_checkpoint(chain))

    tampered = json.loads(json.dumps(wire))
    tampered[1]["reason"] = "changed after signing"
    assert not verify_chain(tampered, trusted)


def test_chain_cli_with_checkpoint(tmp_path):
    """The CLI chain+checkpoint path, using canonical files."""
    private, trusted, chain = _chain(float(2 ** 68))
    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps({"publicKey": public_key_b64url(trusted)}),
                        encoding="utf-8")
    paths = []
    for i, r in enumerate(chain):
        p = tmp_path / f"r{i}.json"
        p.write_bytes(canonical_json(r))
        paths.append(str(p))
    checkpoint_file = tmp_path / "checkpoint.json"
    checkpoint_file.write_text(json.dumps(chain_checkpoint(chain)), encoding="utf-8")

    r = subprocess.run([sys.executable, str(VERIFIER), "--key", str(key_file),
                        "--chain", "--checkpoint", str(checkpoint_file), *paths],
                       capture_output=True, text=True)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
