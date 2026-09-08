"""What one employee is allowed to know about another's work (§86, §12.2-12.5).

There is no channel between employees, and this is why. An employee never
addresses another, never reads another's transcript and never learns that
another exists; everything one hands to the next passes through here, because
the manager decides what is shared and sharing is never the default.

That is a change from what the supervisor did before, and the change is the
point. Carrying every finished result forward into every later task is
*sharing by default* with extra steps: by the fourth task of a six-task plan the
context is five summaries deep, four of them about work the fourth task has
nothing to do with, and the employee pays for all of them in the only currency
a run has. §86 says context is shared intentionally. The intention is already
written down - it is the plan's dependency edges - so this reads them.

**A task sees what it declared it needs.** Its direct dependencies' results, and
the baseline the manager chose for the whole objective (what the workspace
knows, and the acceptance criteria the work is judged against). Nothing else.

**Direct, not transitive.** In a chain t1 -> t2 -> t3, t3 gets t2's result and
not t1's. This is the one decision here that could reasonably go the other way,
and it goes this way because the alternative is "everything, eventually": in
any connected plan the transitive closure of the last task is the whole plan,
which is the default this exists to remove. t2 was given t1's result and its
answer is what t2 made of it - if t1's finding matters to t3, it is in t2's
answer or t2 did its task badly, and that is a fact worth surfacing rather than
papering over.

**A failed dependency hands nothing down.** The supervisor already refuses to
start a task whose dependency failed, so this never comes up in a normal run -
but a half-result quietly presented as what is now true is the worst thing this
object could do, so it is stated here as well.
"""

from __future__ import annotations

from uuid import UUID

import structlog

from domain.tasks.task import Task, TaskStatus
from domain.workforce.assignment import SharedContext
from domain.workforce.protocols import Plan

log = structlog.get_logger(__name__)


class WorkforceCoordinator:
    """The only route a result takes from one employee to another."""

    def __init__(self, plan: Plan, *, baseline: SharedContext | None = None) -> None:
        self._plan = plan
        self._baseline = baseline or SharedContext()
        #: What each finished task handed over, by the id of the *planned* task.
        #: Keyed by the plan's id for it rather than the row's, because a retry
        #: is a new task with a new id and the plan's edges still point at the
        #: original.
        self._results: dict[UUID, tuple[str, tuple[str, ...]]] = {}

    def record(self, planned_id: UUID, finished: Task) -> None:
        """Take what a finished task hands on. A summary, and the files it named.

        Not the transcript. The next employee is being told what is now true,
        which is something the manager states - not a log it is left to read.
        """
        if finished.status is not TaskStatus.COMPLETED or finished.result is None:
            return
        summary = finished.result.summary.strip()
        if not summary:
            return
        self._results[planned_id] = (summary, finished.result.artifacts)

    def context_for(self, planned: Task) -> SharedContext:
        """Everything this task is entitled to see, and nothing more."""
        facts: list[str] = list(self._baseline.facts)
        artifacts: list[str] = list(self._baseline.artifacts)
        shared = 0
        for other in self._plan.depends_on(planned.id):
            handed = self._results.get(other)
            if handed is None:
                continue
            summary, produced = handed
            facts.append(f"{self._goal_of(other)} -> {summary}")
            artifacts.extend(produced)
            shared += 1

        if shared:
            log.info(
                "workforce.context_shared",
                task_id=str(planned.id),
                from_tasks=shared,
                facts=len(facts),
            )
        return SharedContext(
            facts=tuple(facts),
            constraints=self._baseline.constraints,
            artifacts=tuple(dict.fromkeys(artifacts)),
            data=dict(self._baseline.data),
        )

    def results(self) -> tuple[str, ...]:
        """What the plan has produced so far, for the manager's own reading."""
        return tuple(summary for summary, _ in self._results.values())

    def _goal_of(self, task_id: UUID) -> str:
        for task in self._plan.tasks:
            if task.id == task_id:
                return task.goal
        return "an earlier task"
