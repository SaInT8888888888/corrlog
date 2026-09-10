from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import INCORRECT, Score, accuracy, scorer
from inspect_ai.solver import generate


@scorer(metrics=[accuracy()])
def forced_scorer():
    async def score(state, target):
        return Score(value=INCORRECT, explanation="forced INCORRECT")
    return score


@task
def multi_fail_task():
    return Task(
        dataset=[Sample(input=f"q{i}", target="a", id=f"s{i}") for i in range(3)],
        solver=[generate()],
        scorer=forced_scorer(),
    )
