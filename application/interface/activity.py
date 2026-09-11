"""What is happening, in a shape an interface can render without knowing the runtime.

Everything here is a *projection*. The platform already announces progress -
`domain/tasks/progress.py`, emitted by the employee runtime and by Prometheus, fanned
out in memory - and this adds no second stream, no bus and no new emitter. What
it adds is the part every interface would otherwise write for itself: following
one objective across the tasks it delegates, and saying what an event means in
words a person reads.

**The vocabulary stays the runtime's six kinds.** The temptation is fifteen
event types - `EmployeeAssigned`, `BrowserOpened`, `PageNavigated`,
`VerificationStarted`. Each one is a fact the interface would then have to know
about, and each new tool would want its own; `ProgressKind` is deliberately
small for exactly that reason, and expanding it here would move the coupling
rather than remove it. So an activity event carries the kind, a headline the
runtime already wrote, and the payload - and an interface that understands six
kinds understands every tool that will ever be added.

**Following an objective is the real work.** Prometheus stamps its own events with the
objective; its employees do not, because they are running tasks and know
nothing about a manager. So the set of task ids belonging to an objective is
discovered as it goes: seeded from the plans that already exist, extended
whenever the manager announces a task it has just handed out. That logic lived
in the HTTP layer until Phase 13, where a second interface could not reach it.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from domain.errors import StorageNotInitializedError
from domain.tasks.progress import ProgressEvent, ProgressKind, ProgressStream
from domain.tasks.repository import TaskRepository
from domain.workforce.repository import ObjectiveRepository, PlanRepository

#: How long a stream waits with nothing to say before yielding None, so a
#: transport can send whatever keep-alive it uses. A stream that never yields
#: cannot tell a caller "still here" from "gone", and the caller is the only
#: layer that knows what its own connection needs.
IDLE_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    """One thing that just happened, addressed to whoever is watching."""

    task_id: UUID
    kind: ProgressKind
    message: str
    step: int = 0
    objective_id: UUID | None = None
    payload: dict[str, Any] | None = None
    at: datetime | None = None

    @classmethod
    def of(cls, event: ProgressEvent) -> ActivityEvent:
        return cls(
            task_id=event.task_id,
            kind=event.kind,
            message=event.message,
            step=event.step,
            objective_id=event.objective_id,
            payload=event.payload,
            at=event.at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": str(self.task_id),
            "objective_id": str(self.objective_id) if self.objective_id else None,
            "kind": self.kind.value,
            "message": self.message,
            "step": self.step,
            "payload": self.payload or {},
            "at": self.at.isoformat() if self.at else None,
        }

    @property
    def is_final(self) -> bool:
        return self.kind is ProgressKind.RESULT


class Activity:
    """Subscriptions to what is happening, by task or by objective."""

    def __init__(
        self,
        stream: ProgressStream,
        *,
        tasks: TaskRepository,
        objectives: ObjectiveRepository,
        plans: PlanRepository,
    ) -> None:
        self._stream = stream
        self._tasks = tasks
        self._objectives = objectives
        self._plans = plans

    async def for_task(self, task_id: UUID | None) -> AsyncIterator[ActivityEvent | None]:
        """One task's progress, or - with no id - everything happening here.

        A stream watching one task ends when that task does: a finished run has
        nothing further to say, and a caller holding a stream open on one has to
        be told separately to stop listening. The unfiltered stream never ends,
        because there is always another run.

        The subscription is taken out before the task's state is read, so a run
        that finishes between the two is reported rather than missed. `None` is
        yielded when nothing has happened for a while, so a transport can keep
        its own connection alive without reaching into this.
        """
        async with self._stream.subscribe() as queue:
            if task_id is not None:
                watched = await _quietly(self._tasks.get(task_id))
                for past in self._stream.recent(task_id):
                    yield ActivityEvent.of(past)
                if watched is not None and watched.is_terminal:
                    return
            async for event in _drain(queue):
                if event is None:
                    yield None
                    continue
                if task_id is not None and event.task_id != task_id:
                    continue
                activity = ActivityEvent.of(event)
                yield activity
                if task_id is not None and activity.is_final:
                    return

    async def for_objective(self, objective_id: UUID) -> AsyncIterator[ActivityEvent | None]:
        """One objective's progress, and that of every task it starts.

        What makes the trace read as one piece of work rather than as a manager
        talking to itself.
        """
        async with self._stream.subscribe() as queue:
            tracked = await self._tasks_of(objective_id)
            objective = await _quietly(self._objectives.get(objective_id))
            finished = objective is not None and objective.is_terminal

            for past in self._stream.recent(objective_id):
                _track(tracked, past.payload)
                yield ActivityEvent.of(past)
            for task_id in sorted(tracked, key=str):
                for past in self._stream.recent(task_id):
                    yield ActivityEvent.of(past)
            if finished:
                return

            async for event in _drain(queue):
                if event is None:
                    yield None
                    continue
                mine = event.objective_id == objective_id
                if not mine and event.task_id not in tracked:
                    continue
                if mine:
                    _track(tracked, event.payload)
                activity = ActivityEvent.of(event)
                yield activity
                if mine and activity.is_final:
                    return

    async def _tasks_of(self, objective_id: UUID) -> set[UUID]:
        plans = await _quietly(self._plans.for_objective(objective_id))
        return {task.id for plan in plans or () for task in plan.tasks}


def _track(tracked: set[UUID], payload: dict[str, Any]) -> None:
    """Follow a task the manager has just announced it delegated."""
    raw = payload.get("task_id")
    if raw:
        tracked.add(UUID(str(raw)))
    for task in payload.get("tasks") or ():
        if isinstance(task, dict) and task.get("id"):
            tracked.add(UUID(str(task["id"])))


async def _drain(
    queue: asyncio.Queue[ProgressEvent],
) -> AsyncIterator[ProgressEvent | None]:
    while True:
        try:
            yield await asyncio.wait_for(queue.get(), timeout=IDLE_SECONDS)
        except TimeoutError:
            yield None


async def _quietly(awaitable):
    """A machine with no schema yet has no progress to report, not a stack trace.

    Every other operation says "run the migration" plainly. A stream cannot -
    it would arrive as an event nobody can render - and reporting nothing is
    indistinguishable from a quiet run, which is the honest answer here.
    """
    try:
        return await awaitable
    except StorageNotInitializedError:
        return None
