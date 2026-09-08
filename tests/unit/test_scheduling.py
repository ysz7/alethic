"""Phase 12.9: work that starts without anybody asking for it.

The scheduler is deliberately dull, and these are the four things it is not
allowed to get wrong: a missed run is not made up, a schedule already running
does not start again, an event is acted on once, and one schedule's failure is
not the loop's.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta

import pytest

from application.scheduling.scheduler import OBJECTIVE_FINISHED, Scheduler
from domain.scheduling.models import Event, Recurrence, Schedule, Trigger
from domain.workforce.protocols import Objective, ObjectiveResult, ObjectiveStatus
from infrastructure.persistence.schedule_repository import (
    InMemoryEventLog,
    InMemoryScheduleRepository,
)

NOON = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


class RecordingManager:
    """A manager that records what it was asked and answers instantly."""

    def __init__(self, fail: bool = False) -> None:
        self.requests: list[str] = []
        self._fail = fail

    async def receive(self, request: str, workspace_id=None) -> Objective:
        self.requests.append(request)
        return Objective.create(request)

    async def handle_objective(self, objective: Objective) -> ObjectiveResult:
        if self._fail:
            raise RuntimeError("the objective blew up")
        return ObjectiveResult(
            objective_id=objective.id, summary="done", status=ObjectiveStatus.DONE
        )


def scheduler(manager, schedules, events, now=NOON) -> Scheduler:
    return Scheduler(
        manager=manager, schedules=schedules, events=events, clock=lambda: now
    )


# --- The recurrence itself ----------------------------------------------------


def test_an_interval_is_due_immediately_and_a_time_of_day_is_not() -> None:
    hourly = Schedule.create("check", recurrence=Recurrence(every_seconds=3600))
    morning = Schedule.create("check", recurrence=Recurrence(daily_at=time(7, 30)))

    assert hourly.next_due_at == hourly.created_at
    assert morning.next_due_at is not None
    assert morning.next_due_at > morning.created_at


def test_a_missed_run_is_not_made_up() -> None:
    """A laptop shut for the weekend does not owe an hourly schedule the weekend."""
    hourly = Schedule.create(
        "check",
        recurrence=Recurrence(every_seconds=3600),
        next_due_at=NOON - timedelta(days=2),
    )

    moved = hourly.fired(NOON)

    assert moved.next_due_at == NOON + timedelta(hours=1)
    assert moved.runs == 1


def test_an_interval_shorter_than_a_minute_is_refused() -> None:
    with pytest.raises(ValueError, match="shortest interval"):
        Recurrence(every_seconds=5)


def test_a_schedule_fires_on_a_time_or_an_event_and_never_both() -> None:
    with pytest.raises(ValueError, match="not both"):
        Schedule.create(
            "check", recurrence=Recurrence(every_seconds=3600), on_event="inbox.arrived"
        )
    with pytest.raises(ValueError, match="not both"):
        Schedule.create("check")


def test_an_event_driven_schedule_is_never_due_on_the_clock() -> None:
    waiting = Schedule.create("check", on_event="inbox.arrived")

    assert waiting.trigger is Trigger.EVENT
    assert not waiting.is_due(NOON + timedelta(days=365))


# --- One pass -----------------------------------------------------------------


async def test_a_due_schedule_becomes_an_objective() -> None:
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(
        Schedule.create(
            "Summarise the notes", name="daily", recurrence=Recurrence(every_seconds=3600)
        )
    )
    manager = RecordingManager()

    results = await scheduler(manager, schedules, events).tick()

    assert manager.requests == ["Summarise the notes"]
    assert [r.status for r in results] == [ObjectiveStatus.DONE]
    stored = (await schedules.list())[0]
    assert stored.runs == 1
    assert stored.next_due_at == NOON + timedelta(hours=1)
    assert stored.last_objective_id is not None


async def test_a_paused_schedule_does_not_fire() -> None:
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    created = Schedule.create("check", recurrence=Recurrence(every_seconds=3600))
    await schedules.save(created.set_enabled(False))
    manager = RecordingManager()

    await scheduler(manager, schedules, events).tick()

    assert manager.requests == []


async def test_a_schedule_still_running_does_not_start_again() -> None:
    """The commonest scheduling failure, and its symptom is slowness, not an error."""
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(Schedule.create("check", recurrence=Recurrence(every_seconds=60)))

    started = asyncio.Event()
    release = asyncio.Event()

    class SlowManager(RecordingManager):
        async def handle_objective(self, objective):
            started.set()
            await release.wait()
            return await super().handle_objective(objective)

    manager = SlowManager()
    loop = scheduler(manager, schedules, events)

    first = asyncio.create_task(loop.tick())
    await started.wait()
    await loop.tick()  # a second pass while the first is still in flight
    release.set()
    await first

    assert manager.requests == ["check"], "it was asked once"


async def test_an_event_fires_its_schedule_once() -> None:
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(Schedule.create("Triage the inbox", on_event="inbox.arrived"))
    await events.record(Event.create("inbox.arrived", payload={"from": "someone"}))
    manager = RecordingManager()
    loop = scheduler(manager, schedules, events)

    await loop.tick()
    await loop.tick()

    assert len(manager.requests) == 1
    assert "Triage the inbox" in manager.requests[0]
    assert "inbox.arrived" in manager.requests[0], "what triggered it is stated, not merged in"


async def test_an_event_of_another_kind_is_left_alone() -> None:
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(Schedule.create("Triage the inbox", on_event="inbox.arrived"))
    await events.record(Event.create("something.else"))
    manager = RecordingManager()

    await scheduler(manager, schedules, events).tick()

    assert manager.requests == []
    assert not (await events.recent())[0].consumed


async def test_a_failing_objective_does_not_stop_the_loop() -> None:
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(Schedule.create("check", recurrence=Recurrence(every_seconds=3600)))
    manager = RecordingManager(fail=True)

    results = await scheduler(manager, schedules, events).tick()

    assert results == ()
    recorded = await events.recent()
    assert recorded[0].kind == OBJECTIVE_FINISHED
    assert recorded[0].payload["status"] == "FAILED"


async def test_what_a_firing_produced_is_itself_an_event() -> None:
    """So one piece of work can follow another without a second kind of edge."""
    schedules, events = InMemoryScheduleRepository(), InMemoryEventLog()
    await schedules.save(Schedule.create("check", recurrence=Recurrence(every_seconds=3600)))

    await scheduler(RecordingManager(), schedules, events).tick()

    recorded = await events.recent()
    assert [e.kind for e in recorded] == [OBJECTIVE_FINISHED]
    assert recorded[0].payload["status"] == "DONE"
