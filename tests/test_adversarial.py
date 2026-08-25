"""Adversarial tests for corrlog-core: attacks on the correction chain.

Covers the attacks a serious auditor (or hostile party) would try:
  - deletion of an interior record (gap in the chain)
  - reordering records
  - replay / duplicate submission
  - correction-of-correction (linear chain, valid)
  - wrong key / key substitution
  - substitution of the superseded record's content
Run: python3 tests/test_adversarial.py
"""

import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corrlog_core import generate_keypair, record, retract, verify, verify_chain


def _chain(n=3):
    """Build a linear chain of n records: action + (n-1) corrections."""
    priv, _ = generate_keypair()
    r = record(agent_id="a", action_type="memory.write",
               action_args={"x": 1}, private_key=priv)
    chain = [r]
    for i in range(1, n):
        chain.append(retract(prior_record=chain[-1], reason=f"correction {i}",
                             trigger="human_flagged", agent_id="a", private_key=priv))
    return priv, chain


def test_deletion_of_interior_record_detected():
    priv, chain = _chain(3)
    assert verify_chain(chain) is True
    # Delete the middle record: the chain link is now broken.
    deleted = [chain[0], chain[2]]
    assert verify_chain(deleted) is False


def test_reordering_detected():
    priv, chain = _chain(3)
    reordered = [chain[1], chain[0], chain[2]]
    assert verify_chain(reordered) is False


def test_replay_detected():
    # Replaying the same record twice breaks the chain (supersedes digest of
    # the second occurrence points at the wrong predecessor).
    priv, chain = _chain(2)
    replayed = [chain[0], chain[1], chain[1]]
    assert verify_chain(replayed) is False


def test_correction_of_correction_is_valid():
    # A correction correcting a correction is a legitimate linear chain.
    priv, chain = _chain(3)
    assert verify_chain(chain) is True
    assert chain[2]["trigger"] == "human_flagged"
    assert chain[2]["supersedes"]["receiptId"] == chain[1]["correctionId"]


def test_wrong_key_substitution_rejected():
    priv, chain = _chain(2)
    # Verify with a key that did NOT sign the record.
    _, other_pub = generate_keypair()
    assert verify(chain[0], public_key=other_pub) is False
    assert verify(chain[1], public_key=other_pub) is False


def test_substituted_superseded_content_detected():
    # A correction's supersedes.digest is bound to the prior record's bytes.
    # If the attacker swaps in a different (also validly-signed) prior record,
    # the digest no longer matches.
    priv, chain = _chain(2)
    # Build a different valid record and try to pass it as the predecessor.
    other = record(agent_id="a", action_type="memory.write",
                   action_args={"x": 999}, private_key=priv)
    substituted = [other, chain[1]]
    assert verify_chain(substituted) is False


def test_unsigned_tamper_inside_chain_detected():
    priv, chain = _chain(3)
    # Flip a byte in the middle record's reason, then rebuild — signatures must
    # reject the tampered record even if its own hash is recomputed (because
    # the Ed25519 signature over the canonical body no longer verifies).
    tampered = copy.deepcopy(chain)
    tampered[1]["reason"] = "tampered reason"
    assert verify(tampered[1]) is False
    assert verify_chain(tampered) is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} adversarial tests passed.")
