"""Tests for the ProofAgent → ACR adapter.

Exercises the adapter against ProofAgent's REAL data structures (imported from a
clone at /tmp/pa_src when present), falling back to dicts with the exact field
names verified from their source (GateResult.decision/reasons/failed_rules).

Run: python3 tests/test_proofagent.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from cryptography.hazmat.primitives.asymmetric import ed25519

from corrlog_core import verify
from corrlog_proofagent import gate_to_acr, report_to_acr

PRIV = ed25519.Ed25519PrivateKey.generate()


def _real_gate_result(decision: str, reasons: list[str], failed: list[str]):
    """Try to build a REAL ProofAgent GateResult dataclass from a clone, else a dict."""
    src = Path("/tmp/pa_src")
    if src.exists():
        try:
            sys.path.insert(0, str(src / "src"))
            from proofagent_harness.governance_profile import GateResult
            return GateResult(
                decision=decision, reasons=reasons,
                failed_rules=failed, passed_rules=[],
            )
        except Exception:
            pass
    return {"decision": decision, "reasons": reasons, "failed_rules": failed}


def test_pass_produces_no_correction():
    gate = _real_gate_result("pass", [], [])
    out = gate_to_acr(gate_result=gate, private_key=PRIV, agent_id="agent-1")
    assert out is None, "a pass gate must produce no correction receipt"


def test_review_produces_signed_check_failed():
    gate = _real_gate_result("review", ["signoff required"], [])
    rec = gate_to_acr(gate_result=gate, private_key=PRIV, agent_id="agent-1")
    assert rec is not None
    assert rec["trigger"] == "check_failed"
    assert rec["metadata"]["gate_decision"] == "review"
    assert "signoff required" in rec["metadata"]["reasons"]
    assert verify(rec) is True


def test_block_produces_signed_check_failed():
    gate = _real_gate_result(
        "block", ["critical finding"], ["no_forbidden_tool_calls"],
    )
    rec = gate_to_acr(gate_result=gate, private_key=PRIV, agent_id="agent-1")
    assert rec is not None
    assert rec["metadata"]["gate_decision"] == "block"
    assert "critical finding" in rec["metadata"]["reasons"]
    assert "no_forbidden_tool_calls" in rec["metadata"]["reasons"]
    assert verify(rec) is True


def test_report_to_acr_folds_score_and_findings():
    report = {"final_score": 49.0, "findings": [{"a": 1}, {"b": 2}], "warnings": ["low confidence"]}
    rec = report_to_acr(
        report=report, gate_decision="block",
        private_key=PRIV, agent_id="agent-1",
    )
    assert rec is not None
    assert rec["metadata"]["gate_decision"] == "block"
    assert rec["metadata"]["final_score"] == 49.0
    assert rec["metadata"]["findings_count"] == 2
    assert verify(rec) is True


def test_unexpected_decision_raises():
    try:
        gate_to_acr(gate_result={"decision": "banana"}, private_key=PRIV, agent_id="a")
        assert False, "should have raised"
    except ValueError:
        pass


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} ProofAgent adapter tests passed.")
