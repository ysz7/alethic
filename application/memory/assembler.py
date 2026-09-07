"""What a run is told about what happened before it.

A run's context is three things put together, in this order of trust:

1. **the goal** - what was asked, unmodified;
2. **what the delegator passed down** - facts and constraints the manager chose
   deliberately, which are the most recent and the most specific;
3. **what was recalled** - and it is last, because it is the only part nobody
   wrote for this task.

Recall is scoped, always. The query names the workspace, the plan and the
employee, and the store answers within those bounds - an employee never reads
another employee's private memory, and that is enforced where the rows are
rather than trusted here (`domain/memory/access.py`).

The recalled part is labelled as recollection rather than merged into the facts.
A model told "the report is in reports/q3.md" as a fact will act on it; told
"you noted last time that the report was in reports/q3.md" it will check. The
difference matters because memory can be stale in a way an assignment cannot.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from domain.employees.definition import EmployeeDefinition
from domain.memory.models import MemoryItem, MemoryQuery, MemoryScope
from domain.memory.protocols import Memory
from domain.tasks.task import Task
from domain.workforce.assignment import SharedContext

log = structlog.get_logger(__name__)

#: How many recollections a run is given. A budget rather than everything that
#: matched: context is the scarcest thing in a run, and the tenth-best memory
#: costs the same tokens as the best one.
DEFAULT_LIMIT = 6


@dataclass(frozen=True, slots=True)
class AssembledContext:
    """The context for one run, and where each part came from."""

    goal: str
    facts: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    recalled: tuple[MemoryItem, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.facts or self.constraints or self.recalled)

    def recollections(self) -> tuple[str, ...]:
        """The remembered part, as the lines a prompt shows."""
        return tuple(item.content.strip() for item in self.recalled if item.content.strip())


class ContextAssembler:
    """Goal, assignment and memory, assembled into one context (§9.6)."""

    def __init__(self, memory: Memory, *, limit: int = DEFAULT_LIMIT) -> None:
        self._memory = memory
        self._limit = limit

    async def assemble(
        self,
        task: Task,
        definition: EmployeeDefinition,
        context: SharedContext | None = None,
    ) -> AssembledContext:
        passed = context or SharedContext()
        recalled = await self._recall(task, definition, passed)
        return AssembledContext(
            goal=task.goal,
            facts=passed.facts,
            constraints=passed.constraints,
            recalled=recalled,
        )

    async def _recall(
        self, task: Task, definition: EmployeeDefinition, context: SharedContext
    ) -> tuple[MemoryItem, ...]:
        query = MemoryQuery(
            # The goal plus what came with it: an assignment's facts name the
            # subject in words the goal often leaves out.
            text=" ".join((task.goal, *context.facts)),
            workspace_id=task.workspace_id,
            scopes=frozenset(
                {MemoryScope.WORKSPACE, MemoryScope.PLAN, MemoryScope.EMPLOYEE_PRIVATE}
            ),
            employee_id=definition.id,
            plan_id=task.plan_id,
            task_id=task.id,
            limit=self._limit,
        )
        try:
            items = await self._memory.recall(query)
        except Exception as error:
            # Memory is an improvement to a run, never a precondition for one.
            log.warning("memory.recall_failed", task_id=str(task.id), error=str(error))
            return ()
        if items:
            log.info(
                "memory.recalled",
                task_id=str(task.id),
                employee=definition.name,
                items=len(items),
            )
        return tuple(items)
