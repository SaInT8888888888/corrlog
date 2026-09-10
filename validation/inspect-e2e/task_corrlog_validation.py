"""Minimal real Inspect task for CorrLog end-to-end validation.

Uses mockllm so the run is fully offline and deterministic. The scorer forces
INCORRECT so the corrlog hook has a real failing sample to react to.
"""
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import CORRECT, INCORRECT, Score, accuracy, scorer
from inspect_ai.solver import generate


@scorer(metrics=[accuracy()])
def forced_scorer(verdict: str = INCORRECT):
    async def score(state, target):
        return Score(value=verdict, explanation=f"forced {verdict} for validation")
    return score


@task
def validation_task():
    return Task(
        dataset=[
            Sample(input="What is 2+2?", target="4", id="sample-pass"),
        ],
        solver=[generate()],
        scorer=forced_scorer(INCORRECT),
    )


@task
def validation_task_pass():
    return Task(
        dataset=[Sample(input="What is 2+2?", target="4", id="sample-ok")],
        solver=[generate()],
        scorer=forced_scorer(CORRECT),
    )
