"""Alethic accepts a result on the evidence, not on the report (§88).

The employee runtime already verifies each task against its own goal, and that
is necessary and not sufficient: the witness is the run that would report
finishing either way. This is the manager's own check, and it is deliberately
*not* a second opinion from a second model. It is a fact about what the task
did, read off the record the task left behind.

The fact it reads is narrow and was expensive to learn. A task that reached for
tools and had every one of them refused or fail has not done the work, however
its closing message reads - and the first full validation run produced exactly
that answer, an employee reporting success having touched nothing. A model
asked to notice this would sometimes notice it. A count of successful tool calls
notices it every time, costs nothing, and cannot be talked out of it.

Two things it deliberately does **not** do.

**It does not fail a task that used no tools.** Judgement is real work: deciding,
comparing, writing an answer from what was passed down. Requiring evidence of
action from work whose product is a sentence would reject the tasks the platform
is best at.

**It does not judge quality.** Whether the answer is good is the verifier's
question and the objective's criteria are where it is asked. This one answers
only whether anything happened, which is the question no amount of reading the
answer can settle.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.tasks.task import Task, TaskStatus


@dataclass(frozen=True, slots=True)
class Acceptance:
    """Whether the manager takes this result, and what to do if not."""

    accepted: bool
    reason: str = ""
    #: True when the reason the work did not happen is that the employee was not
    #: allowed to do it. Somebody else may be, so it is worth reassigning rather
    #: than replanning - the same distinction `supervisor.classify` makes.
    refused: bool = False

    @classmethod
    def taken(cls) -> Acceptance:
        return cls(accepted=True)


def accept(task: Task) -> Acceptance:
    """Judge one finished task on what it did, not on what it said."""
    if task.status is not TaskStatus.COMPLETED:
        # Not this function's question. A task that failed already says so, and
        # the supervisor decides what a failure calls for.
        return Acceptance.taken()

    attempted = 0
    succeeded = 0
    refused = 0
    for raw in _observations(task):
        attempted += 1
        if raw.get("succeeded", True):
            succeeded += 1
        elif (raw.get("details") or {}).get("refused"):
            refused += 1

    if attempted == 0 or succeeded > 0:
        return Acceptance.taken()

    if refused:
        return Acceptance(
            accepted=False,
            reason=(
                f"It reported success, but all {attempted} of its tool calls were "
                f"refused ({refused} without permission or approval) and none reached "
                "the world."
            ),
            refused=True,
        )
    return Acceptance(
        accepted=False,
        reason=(
            f"It reported success, but all {attempted} of its tool calls failed and "
            "nothing it tried to do actually happened."
        ),
    )


def _observations(task: Task) -> tuple[dict, ...]:
    raw = (task.result.output.get("observations") if task.result else None) or ()
    return tuple(item for item in raw if isinstance(item, dict))
