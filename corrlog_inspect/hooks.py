"""Inspect hook that emits one signed ACR receipt per failing sample.

Grounded against inspect_ai 0.3.260:
  * register with @hooks(name, description) on a Hooks subclass
  * async on_sample_end(data: SampleEnd)
  * data.sample: EvalSample; data.sample.scores: dict[str, Score] | None
  * Score.value compared to INCORRECT ('I')
  * async on_task_start(data: TaskStart) — data.spec.model is the evaluated
    model (a string), captured here so the receipt's agent_id is the actual
    model, not the sample pointer.

Design choices worth knowing:
  * enabled() returns True only when a signing key is configured, so merely
    installing the package changes nothing until you opt in via env var.
  * agent_id is the evaluated MODEL (from spec.model at task start); the sample
    reference stays a separate field (subject_ref). That keeps "who did the
    thing" distinct from "what was evaluated".
  * One receipt per failing *sample*, aggregating every scorer that returned
    INCORRECT into that receipt's metadata — not one receipt per scorer.
  * Signing failures are caught and logged, never raised: a correction-log hook
    must not be able to fail an eval run.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from inspect_ai.hooks import Hooks, SampleEnd, TaskStart, hooks
from inspect_ai.scorer import INCORRECT, Score

from ._corrlog import CorrlogSigner, Signer, build_correction

logger = logging.getLogger(__name__)

# Env var holding the operator's signing key (Ed25519 seed, base64url or hex).
# corrlog_core.load_private_key parses it.
KEY_ENV = "CORRLOG_SIGNING_KEY"


def _is_failing(score: Score) -> bool:
    """True if this score represents a failure (INCORRECT).

    Inspect's canonical incorrect value is INCORRECT ('I'). Scorers may also
    yield richer values; we treat only a top-level INCORRECT as failing and
    leave anything else to explicit configuration rather than guessing.
    """
    return score.value == INCORRECT


@hooks(
    name="corrlog_receipt",
    description="Emit a signed ACR correction receipt when a sample scores INCORRECT.",
)
class CorrlogReceiptHook(Hooks):
    def __init__(self, signer: Signer | None = None) -> None:
        # Allow injection for testing; default to the real corrlog seam.
        key = os.environ.get(KEY_ENV, "")
        self._signer: Signer | None = signer or (CorrlogSigner(key) if key else None)
        # The evaluated model per eval, captured at task start (spec.model).
        self._model_by_eval: dict[str, str] = {}

    @classmethod
    def enabled(cls) -> bool:
        # Opt-in: do nothing unless a signing key is present in the environment.
        return bool(os.environ.get(KEY_ENV))

    async def on_task_start(self, data: TaskStart) -> None:
        # spec.model is the evaluated model string (e.g. "openai/gpt-4o").
        self._model_by_eval[data.eval_id] = data.spec.model

    async def on_sample_end(self, data: SampleEnd) -> None:
        sample = data.sample
        scores = sample.scores or {}
        failing = {name: s.value for name, s in scores.items() if _is_failing(s)}
        if not failing:
            return

        subject_ref = f"inspect:{data.eval_id}/{data.sample_id}"
        # agent_id is the actual model when we captured it; fall back to the
        # sample pointer only if task-start never fired (defensive).
        agent_id = self._model_by_eval.get(data.eval_id) or subject_ref

        detail = (
            f"Inspect sample {data.sample_id} scored INCORRECT on "
            f"{', '.join(sorted(failing))}"
        )
        context: dict[str, Any] = {
            "eval_id": data.eval_id,
            "run_id": data.run_id,
            "sample_id": data.sample_id,
            "epoch": sample.epoch,
        }
        correction = build_correction(
            agent_id=agent_id,
            subject_ref=subject_ref,
            detail=detail,
            failing_scorers=failing,
            context=context,
        )

        signer = self._signer
        if signer is None:  # enabled() should prevent this, but be defensive
            return
        try:
            signer.sign(correction)
        except Exception:
            # Never let receipt emission break the eval run.
            logger.exception("corrlog: failed to emit correction receipt")
