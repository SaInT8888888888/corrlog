"""Tests for corrlog-inspect.

Two layers:

1. Inspect-side tests run against the REAL inspect_ai classes (SampleEnd,
   EvalSample, Score) with only the corrlog core stubbed via FakeSigner.
2. Integration tests prove the seam is actually WIRED: a real CorrlogSigner
   signs with a real key, and corrlog_core.verify accepts the result.

Run: python3 tests/test_inspect.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from inspect_ai.hooks import SampleEnd, TaskStart
from inspect_ai.log import EvalSample
from inspect_ai.scorer import CORRECT, INCORRECT, Score

from corrlog_core import generate_keypair, public_key_b64url, verify
from corrlog_inspect._corrlog import CorrlogSigner, Signer, build_correction
from corrlog_inspect.hooks import CorrlogReceiptHook


class FakeSigner:
    """Stands in for the corrlog core. Records what it was asked to sign."""

    def __init__(self) -> None:
        self.signed: list[dict[str, Any]] = []

    def sign(self, correction: dict[str, Any]) -> dict[str, Any]:
        self.signed.append(correction)
        return {"receipt": True, **correction}


class ExplodingSigner:
    def sign(self, correction: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("corrlog core unavailable")


def _sample(scores) -> EvalSample:
    return EvalSample(id="s1", epoch=1, input="q", target="a", scores=scores)


def _event(sample: EvalSample) -> SampleEnd:
    return SampleEnd(
        eval_set_id=None,
        run_id="run-1",
        eval_id="eval-1",
        sample_id=str(sample.id),
        sample=sample,
    )


def _task_start(model: str = "openai/gpt-4o") -> TaskStart:
    # Build a minimal EvalSpec carrying the model, as TaskStart.spec.
    from inspect_ai.log._log import EvalConfig, EvalDataset, EvalSpec
    spec = EvalSpec(
        eval_set_id=None,
        eval_id="eval-1",
        run_id="run-1",
        task="mytask",
        dataset=EvalDataset(),
        model=model,
        created="2026-08-26T00:00:00+00:00",
        config=EvalConfig(),
    )
    return TaskStart(
        eval_set_id=None,
        run_id="run-1",
        eval_id="eval-1",
        spec=spec,
        plan=None,
    )


def _run(hook: CorrlogReceiptHook, event: SampleEnd) -> None:
    asyncio.run(hook.on_sample_end(event))


# ── Inspect-side behaviour (corrlog stubbed) ──────────────────────────────

def test_fakesigner_is_a_signer() -> None:
    assert isinstance(FakeSigner(), Signer)


def test_correct_sample_emits_nothing() -> None:
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    _run(hook, _event(_sample({"match": Score(value=CORRECT)})))
    assert signer.signed == []


def test_incorrect_sample_emits_one_receipt() -> None:
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    asyncio.run(hook.on_task_start(_task_start("openai/gpt-4o")))
    _run(hook, _event(_sample({"match": Score(value=INCORRECT)})))
    assert len(signer.signed) == 1
    c = signer.signed[0]
    assert c["trigger"] == "check_failed"
    assert c["fix_type"] == "other"
    assert c["agent_id"] == "openai/gpt-4o"
    assert c["subject_ref"] == "inspect:eval-1/s1"
    assert c["metadata"]["severity"] == "incorrect"
    assert c["metadata"]["failing_scorers"] == {"match": INCORRECT}
    assert c["metadata"]["source"] == "inspect_ai"


def test_multiple_failing_scorers_aggregate_into_one_receipt() -> None:
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    scores = {
        "match": Score(value=INCORRECT),
        "safety": Score(value=INCORRECT),
        "helpfulness": Score(value=CORRECT),
    }
    _run(hook, _event(_sample(scores)))
    assert len(signer.signed) == 1  # one receipt per sample, not per scorer
    failing = signer.signed[0]["metadata"]["failing_scorers"]
    assert set(failing) == {"match", "safety"}  # correct scorer excluded


def test_no_scores_emits_nothing() -> None:
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    sample = EvalSample(id="s1", epoch=1, input="q", target="a", scores=None)
    _run(hook, _event(sample))
    assert signer.signed == []


def test_signing_failure_is_non_fatal() -> None:
    hook = CorrlogReceiptHook(signer=ExplodingSigner())
    # Must not raise: a receipt hook may never break the eval run.
    _run(hook, _event(_sample({"match": Score(value=INCORRECT)})))


def test_build_correction_shape_is_pure() -> None:
    c = build_correction(
        agent_id="openai/gpt-4o",
        subject_ref="inspect:e/s",
        detail="d",
        failing_scorers={"match": "I"},
        context={"eval_id": "e"},
    )
    assert c["trigger"] == "check_failed"
    assert c["fix_type"] == "other"
    assert c["agent_id"] == "openai/gpt-4o"
    assert c["subject_ref"] == "inspect:e/s"
    assert c["metadata"]["failing_scorers"] == {"match": "I"}
    assert c["metadata"]["eval_id"] == "e"


def test_task_start_captures_model_identity() -> None:
    """on_task_start populates the model map, and the receipt's agent_id is the model."""
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    asyncio.run(hook.on_task_start(_task_start("openai/gpt-4o")))
    assert hook._model_by_eval["eval-1"] == "openai/gpt-4o"
    _run(hook, _event(_sample({"match": Score(value=INCORRECT)})))
    assert signer.signed[0]["agent_id"] == "openai/gpt-4o"
    # and the sample pointer stays distinct
    assert signer.signed[0]["subject_ref"] == "inspect:eval-1/s1"


def test_agent_id_falls_back_to_subject_ref_without_task_start() -> None:
    """Defensive: if task-start never fired, agent_id degrades to the sample pointer."""
    signer = FakeSigner()
    hook = CorrlogReceiptHook(signer=signer)
    _run(hook, _event(_sample({"match": Score(value=INCORRECT)})))
    assert signer.signed[0]["agent_id"] == "inspect:eval-1/s1"


# ── Integration: the seam is actually WIRED ───────────────────────────────

def _seed_b64url(priv) -> str:
    import base64
    from cryptography.hazmat.primitives import serialization
    raw = priv.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def test_real_signer_produces_verifiable_receipt() -> None:
    priv, pub = generate_keypair()
    signer = CorrlogSigner(_seed_b64url(priv))

    correction = build_correction(
        agent_id="openai/gpt-4o",
        subject_ref="inspect:eval-1/s1",
        detail="sample s1 scored INCORRECT on match",
        failing_scorers={"match": "I"},
        context={"eval_id": "eval-1", "run_id": "run-1", "sample_id": "s1", "epoch": 1},
    )
    receipt = signer.sign(correction)

    # The receipt is a real signed ACR correction record.
    assert receipt["trigger"] == "check_failed"
    assert receipt["fix"]["type"] == "other"
    # agent_id is the model, not the sample pointer
    assert receipt["agent"]["id"] == "openai/gpt-4o"
    # verifies against its own embedded key, AND against the pinned key
    assert verify(receipt) is True
    assert verify(receipt, public_key=pub) is True
    # the verdict is in structured metadata
    assert receipt["metadata"]["severity"] == "incorrect"
    assert receipt["metadata"]["failing_scorers"] == {"match": "I"}


def test_real_signer_end_to_end_via_hook() -> None:
    """The full path: hook detects INCORRECT → CorrlogSigner signs → verifiable."""
    priv, pub = generate_keypair()
    import os
    os.environ["CORRLOG_SIGNING_KEY"] = _seed_b64url(priv)
    try:
        hook = CorrlogReceiptHook()  # picks up the key from env
        assert hook.enabled() is True
        # use a real signer via the seam, capture by monkeypatching sign
        signed = []
        hook._signer = CorrlogSigner(os.environ["CORRLOG_SIGNING_KEY"])
        # wrap to capture
        real_sign = hook._signer.sign
        def _capture(c):
            r = real_sign(c)
            signed.append(r)
            return r
        hook._signer.sign = _capture  # type: ignore[method-assign]
        _run(hook, _event(_sample({"match": Score(value=INCORRECT)})))
        assert len(signed) == 1
        assert verify(signed[0], public_key=pub) is True
    finally:
        os.environ.pop("CORRLOG_SIGNING_KEY", None)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(fns)} corrlog-inspect tests passed.")
