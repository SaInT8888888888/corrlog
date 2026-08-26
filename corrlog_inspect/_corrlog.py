"""The corrlog seam — wiring between Inspect's detection and corrlog's signing.

Two parts:

* `build_correction(...)` is pure and fully tested: it turns a detected failing
  score into the ACR correction *payload* (trigger=check_failed, fix_type=other,
  structured verdict metadata). No corrlog import, no signing.
* `Signer` is the boundary. `CorrlogSigner` is the real one, wired to
  corrlog_core; a `FakeSigner` in the tests exercises everything else without
  corrlog present.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# corrlog's correction schema, as established by the spec:
#   trigger  ∈ {supersede, check_failed, human_flagged, self_correction}
#   fix_type ∈ {replace, delete, rollback, noop, other}
# A gate/scorer verdict is a detection, not a content fix, so:
TRIGGER = "check_failed"
FIX_TYPE = "other"  # the verdict itself travels in structured metadata (below)


def build_correction(
    *,
    agent_id: str,
    subject_ref: str,
    detail: str,
    failing_scorers: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Build the unsigned ACR correction payload for a failed Inspect sample.

    Pure function: no corrlog import, no signing, no I/O. This is the part that
    encodes *what* the receipt asserts; `Signer.sign` is the part that makes it
    a tamper-evident, attributable record.

    `agent_id` is WHO performed the action being corrected (the evaluated
    model); `subject_ref` is WHAT was evaluated (the sample pointer). They are
    distinct, and the receipt keeps them distinct.

    The verdict is placed in structured metadata with an enum-style `severity`
    key rather than free text, so a downstream consumer can filter on it as a
    first-class field (the schema note from review). If/when the core grows a
    typed severity slot, promote it out of metadata.
    """
    return {
        "trigger": TRIGGER,
        "fix_type": FIX_TYPE,
        "agent_id": agent_id,
        "subject_ref": subject_ref,
        "detail": detail,
        "metadata": {
            "source": "inspect_ai",
            "severity": "incorrect",  # enum-style, not free text
            "failing_scorers": failing_scorers,  # {scorer_name: score_value}
            **context,  # eval_id / sample_id / run_id / task / model, etc.
        },
    }


@runtime_checkable
class Signer(Protocol):
    """Anything that can turn a correction payload into a signed ACR receipt."""

    def sign(self, correction: dict[str, Any]) -> dict[str, Any]:
        ...


class CorrlogSigner:
    """Real signer, wired to the corrlog core.

    The correction payload from `build_correction` is translated into corrlog's
    two-step model:
      record(action) → the eval sample as an action record
      retract(...)   → the correction superseding it (trigger=check_failed)
    The returned receipt is the signed, hash-chained correction record that
    `corrlog_core.verify` and the standalone verifier accept under the pinned
    public half of this key.
    """

    def __init__(self, key: str) -> None:
        # `key` is the operator's Ed25519 seed (base64url or hex), read from
        # CORRLOG_SIGNING_KEY. corrlog_core.load_private_key parses it.
        self._key = key

    def sign(self, correction: dict[str, Any]) -> dict[str, Any]:
        from corrlog_core import load_private_key, record, retract

        priv = load_private_key(self._key)

        agent_id = correction["agent_id"]      # the evaluated model
        subject_ref = correction["subject_ref"]  # the sample pointer
        meta = dict(correction.get("metadata") or {})

        # The evaluated model is the "agent" whose action is being corrected;
        # the sample reference is the action target. They stay separate.
        action = record(
            agent_id=agent_id,
            principal_id="inspect-operator",
            principal_type="organization",
            action_type="eval.sample",
            action_target=subject_ref,
            action_result=meta.get("failing_scorers"),
            private_key=priv,
        )

        return retract(
            prior_record=action,
            reason=correction["detail"],
            trigger=correction["trigger"],
            agent_id=agent_id,
            private_key=priv,
            principal_id="inspect-operator",
            principal_type="organization",
            fix_type=correction["fix_type"],
            fix_note=correction["detail"],
            metadata=meta,
        )
