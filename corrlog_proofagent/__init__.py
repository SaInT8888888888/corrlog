"""corrlog adapter for ProofAgent Harness — emit a signed ACR correction when a
governance gate returns `review` or `block`.

ProofAgent (https://github.com/ProofAgent-ai/proofagent-harness) stress-tests
agents adversarially and produces a `Report`, plus a governance `GateResult`
with `decision ∈ {pass, review, block}` (see their `governance_profile.py`).

This adapter turns a gate failure into a signed ACR correction receipt:

    ProofAgent gate decision (review/block)
        → corrlog correction record (trigger = `check_failed`)
        → signed by the OPERATOR's key (the party running ProofAgent)

It is import-safe: it parses ProofAgent's *output shapes* (dicts / dataclasses
exposed via attribute or key access) and never imports ProofAgent itself, so it
works whether or not the harness is installed alongside corrlog.

The mapping (one line, deliberately honest):
    pass      → no correction (nothing failed)
    review    → correction, trigger=check_failed, fix_type=review
    block     → correction, trigger=check_failed, fix_type=block

The receipt records that an independent evaluator caught a failure — it does NOT
claim the failure is the only one, or that the vendor disclosed it voluntarily.
That is the completeness boundary (SPEC §2, §9): the operator's key signs what
the gate *did* observe, nothing more.
"""
from __future__ import annotations

from typing import Any

from corrlog_core import record, retract

# Trigger used for every ProofAgent gate failure. ProofAgent's gate is an
# independent detector, so a failed gate is a check_failed — not a
# self_correction (the agent isn't confessing) and not a supersede (nothing is
# being rewritten, a verdict is being recorded).
TRIGGER = "check_failed"

# A gate verdict is not a replace/delete/rollback — it is a recorded
# detection of a failure, so the fix_type is "other" and the specific
# decision (review vs block) travels in corrected_content + metadata.
FIX_TYPE = "other"


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Read a field from a dataclass, pydantic model, or dict — whichever ProofAgent
    hands us (their GateResult is a dataclass; a saved report is a dict)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    if hasattr(obj, key):
        return getattr(obj, key, default)
    return default


def _decision(obj: Any) -> str | None:
    d = _get(obj, "decision")
    if d is None and isinstance(obj, dict):
        # some paths surface the gate decision under 'verdict' or 'pai'
        for alt in ("verdict", "pai", "gate_decision"):
            if isinstance(obj.get(alt), dict):
                d = _get(obj[alt], "decision")
                if d:
                    break
    return str(d).strip().lower() if d is not None else None


def _reasons(obj: Any) -> list[str]:
    r = _get(obj, "reasons", []) or []
    if isinstance(r, str):
        r = [r]
    fr = _get(obj, "failed_rules", []) or []
    if isinstance(fr, str):
        fr = [fr]
    return [str(x) for x in list(r) + list(fr) if x]


def gate_to_acr(
    *,
    gate_result: Any,
    private_key: Any,
    agent_id: str,
    principal_id: str = "unknown",
    principal_type: str = "organization",
    agent_name: str | None = None,
    action_target: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any] | None:
    """Convert a ProofAgent gate result into a signed ACR correction receipt.

    Returns ``None`` when the gate decision is ``pass`` (no failure to record).
    Returns a signed correction record otherwise (trigger=check_failed).

    ``gate_result`` may be a ProofAgent ``GateResult`` dataclass, a dict from a
    saved report, or any object exposing ``decision`` / ``reasons`` /
    ``failed_rules``.
    """
    decision = _decision(gate_result)
    if decision is None:
        raise ValueError("gate_result has no readable 'decision' field")
    if decision == "pass":
        return None

    if decision not in ("review", "block"):
        raise ValueError(
            f"unexpected gate decision {decision!r} (expected pass/review/block)"
        )

    reasons = _reasons(gate_result)
    reason = "; ".join(reasons) if reasons else f"governance gate returned {decision}"

    # The gate decision + reasons are the human-readable payload of this record,
    # so they live in metadata (stored verbatim). corrected_content is for actual
    # replacement content, which a gate verdict does not produce.
    meta = dict(metadata or {})
    meta["gate_decision"] = decision
    meta["reasons"] = reasons

    # An action record representing the evaluation run, so the correction can
    # supersede it and the chain is meaningful.
    action = record(
        agent_id=agent_id,
        agent_name=agent_name,
        principal_id=principal_id,
        principal_type=principal_type,
        action_type="agent.evaluation",
        action_target=action_target,
        action_args={"harness": "proofagent"},
        action_result={"gate_decision": decision},
        private_key=private_key,
        correction_id=None,  # fresh id for the action record
        timestamp=timestamp,
    )

    fix_type = FIX_TYPE

    return retract(
        prior_record=action,
        reason=reason,
        trigger=TRIGGER,
        agent_id=agent_id,
        private_key=private_key,
        principal_id=principal_id,
        principal_type=principal_type,
        fix_type=fix_type,
        fix_note=(
            f"ProofAgent governance gate returned {decision}. "
            "Operator attests that this evaluator caught the failure."
        ),
        metadata=meta,
        correction_id=correction_id,
        timestamp=timestamp,
    )


def report_to_acr(
    *,
    report: Any,
    gate_decision: str,
    private_key: Any,
    agent_id: str,
    principal_id: str = "unknown",
    principal_type: str = "organization",
    agent_name: str | None = None,
    action_target: str | None = None,
    metadata: dict[str, Any] | None = None,
    correction_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any] | None:
    """Convenience wrapper: take a ProofAgent ``Report`` (or saved dict) plus an
    explicit gate decision, and emit the correction.

    Use this when you have the full Report (final_score, findings, etc.) and a
    separately computed gate decision. The report's score and finding count are
    folded into the correction's metadata so the receipt is self-describing.
    """
    final_score = _get(report, "final_score")
    findings = _get(report, "findings", []) or []
    n_findings = len(findings) if hasattr(findings, "__len__") else None

    meta = dict(metadata or {})
    if final_score is not None:
        meta["final_score"] = final_score
    if n_findings is not None:
        meta["findings_count"] = n_findings

    return gate_to_acr(
        gate_result={"decision": gate_decision, "reasons": _get(report, "warnings", [])},
        private_key=private_key,
        agent_id=agent_id,
        principal_id=principal_id,
        principal_type=principal_type,
        agent_name=agent_name,
        action_target=action_target,
        metadata=meta or None,
        correction_id=correction_id,
        timestamp=timestamp,
    )
