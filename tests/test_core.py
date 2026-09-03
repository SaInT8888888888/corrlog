"""Tests for corrlog-core. Run: python3 -m pytest tests/ -v  (or python3 tests/test_core.py)"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from corrlog_core import (
    canonical_json, generate_keypair, record, retract, unknown, verify, verify_chain,
    tamper_evident, MemorySink, JsonlSink,
)


def test_canonical_json_sorts_keys():
    assert canonical_json({"b": 1, "a": {"d": 2, "c": 3}}) == b'{"a":{"c":3,"d":2},"b":1}'


def test_record_and_verify_roundtrip():
    priv, _ = generate_keypair()
    r = record(
        agent_id="agent-001", agent_name="forecast-agent",
        action_type="memory.write", action_args={"project": "zespri", "topic": "yield"},
        action_result={"status": "ok"}, private_key=priv,
    )
    assert verify(r) is True


def test_signature_detects_tampering():
    priv, _ = generate_keypair()
    r = record(agent_id="a", action_type="api.call", action_args={"x": 1}, private_key=priv)
    assert verify(r) is True
    # Tamper with the reason field after signing.
    r2 = dict(r)
    r2["reason"] = "tampered"
    assert verify(r2) is False
    assert tamper_evident(r2) is False


def test_retract_supersedes_and_chain_verifies():
    priv, _ = generate_keypair()
    r1 = record(agent_id="a", action_type="payment.execute",
                action_args={"amount": "100.00", "recipient": "acct-x"},
                private_key=priv)
    # A correction: check_failed (e.g. idempotency guard caught a duplicate).
    c1 = retract(prior_record=r1, reason="duplicate payment on retry",
                 trigger="check_failed", agent_id="a", private_key=priv,
                 fix_type="rollback", fix_note="reversed duplicate charge")
    assert verify(c1) is True
    # The chain (receipt -> correction) must verify.
    assert verify_chain([r1, c1]) is True
    # And the supersedes digest must point at r1's canonical bytes.
    assert c1["supersedes"]["digest"]["alg"] == "sha256"


def test_chain_detects_broken_link():
    priv, _ = generate_keypair()
    r1 = record(agent_id="a", action_type="x", private_key=priv)
    r2 = record(agent_id="a", action_type="y", private_key=priv)  # unrelated
    c = retract(prior_record=r1, reason="wrong", trigger="human_flagged",
                agent_id="a", private_key=priv)
    # c supersedes r1, not r2 — a chain [r2, c] is broken.
    assert verify_chain([r2, c]) is False


def test_rejects_bad_trigger():
    priv, _ = generate_keypair()
    r1 = record(agent_id="a", action_type="x", private_key=priv)
    try:
        retract(prior_record=r1, reason="r", trigger="bogus_trigger",
                agent_id="a", private_key=priv)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_memory_and_jsonl_sinks():
    priv, _ = generate_keypair()
    r = record(agent_id="a", action_type="x", private_key=priv)

    m = MemorySink()
    m.append(r)
    assert len(m.all()) == 1
    assert m.get(r["correctionId"]) == r

    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
        path = f.name
    j = JsonlSink(path)
    j.append(r)
    loaded = j.all()
    assert len(loaded) == 1
    assert verify(loaded[0]) is True
    os.unlink(path)


def test_self_authenticating_verify_and_explicit_key():
    priv, pub = generate_keypair()
    r = record(agent_id="a", action_type="x", private_key=priv)
    # No key -> uses embedded public key.
    assert verify(r) is True
    # Explicit key -> pins trust.
    assert verify(r, public_key=pub) is True
    # Wrong key -> fails.
    _, other_pub = generate_keypair()
    assert verify(r, public_key=other_pub) is False


def test_retract_carries_source_field():
    """A correction can record WHERE the correct value came from - the trust
    field that turns 'the value changed' into 'the value changed, here is the
    proof of where the correct value lives'."""
    priv, _ = generate_keypair()
    r = record(agent_id="a", action_type="sql.write", private_key=priv)
    c = retract(prior_record=r, reason="table name was guessed, not confirmed",
                trigger="human_flagged", agent_id="a", private_key=priv,
                fix_type="replace", corrected_content={"table": "marc"},
                source_type="schema", source_reference="sap/fssi/marc.fields")
    assert verify(c) is True
    assert c["fix"]["source"] == {"type": "schema", "reference": "sap/fssi/marc.fields"}
    # Without a source, the field is simply absent (backward compatible).
    c2 = retract(prior_record=r, reason="x", trigger="check_failed",
                 agent_id="a", private_key=priv)
    assert "source" not in c2["fix"]


def test_retract_rejects_source_without_reference():
    priv, _ = generate_keypair()
    r = record(agent_id="a", action_type="x", private_key=priv)
    try:
        retract(prior_record=r, reason="r", trigger="human_flagged",
                agent_id="a", private_key=priv, source_type="schema")
        assert False, "expected ValueError (source_type without reference)"
    except ValueError:
        pass
    try:
        retract(prior_record=r, reason="r", trigger="human_flagged",
                agent_id="a", private_key=priv, source_type="bogus_type",
                source_reference="ref")
        assert False, "expected ValueError (invalid source type)"
    except ValueError:
        pass


def test_unknown_records_uncertainty():
    """An agent can record 'I don't know' as a signed first-class event,
    instead of guessing or staying silent."""
    priv, _ = generate_keypair()
    u = unknown(agent_id="a", private_key=priv, subject="fssi.mara field map",
                note="not confirmed against the schema")
    assert verify(u) is True
    assert u["kind"] == "unknown"
    assert u["subject"] == "fssi.mara field map"
    # It has no supersedes pointer and no fix - it is not a correction.
    assert "supersedes" not in u
    assert "fix" not in u
    # Tampering is still detected.
    u2 = dict(u)
    u2["note"] = "tampered"
    assert verify(u2) is False


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
