"""Schedules and events against a real SQLite file (§12.9).

The point of storing them at all is that they survive the process, so these run
against the same file-backed database the product uses rather than a fake.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.scheduling.models import Event, Recurrence, Schedule
from infrastructure.persistence.schedule_repository import (
    SqliteEventLog,
    SqliteScheduleRepository,
)

NOON = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


async def test_a_schedule_survives_being_written_and_read(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = SqliteScheduleRepository(session_factory)
    created = Schedule.create(
        "Summarise the notes",
        name="daily-notes",
        recurrence=Recurrence(daily_at=time(7, 30)),
    )

    await store.save(created)
    read = await store.get(created.id)

    assert read is not None
    assert read.request == "Summarise the notes"
    assert read.recurrence == Recurrence(daily_at=time(7, 30))
    assert read.next_due_at == created.next_due_at
    assert read.enabled


async def test_due_answers_about_a_moment_rather_than_now(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`now` is passed in, so the whole of this can be tested without waiting."""
    store = SqliteScheduleRepository(session_factory)
    hourly = Schedule.create(
        "check", recurrence=Recurrence(every_seconds=3600), next_due_at=NOON
    )
    await store.save(hourly)

    assert await store.due(NOON - timedelta(minutes=1)) == []
    assert [s.id for s in await store.due(NOON)] == [hourly.id]

    await store.save(hourly.fired(NOON))
    assert await store.due(NOON) == []
    assert [s.id for s in await store.due(NOON + timedelta(hours=1))] == [hourly.id]


async def test_a_paused_schedule_is_never_due(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = SqliteScheduleRepository(session_factory)
    created = Schedule.create(
        "check", recurrence=Recurrence(every_seconds=3600), next_due_at=NOON
    )
    await store.save(created.set_enabled(False))

    assert await store.due(NOON + timedelta(days=1)) == []


async def test_an_event_is_claimed_exactly_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The check and the write are one statement, so two passes cannot both win."""
    log = SqliteEventLog(session_factory)
    event = Event.create("inbox.arrived", payload={"from": "someone"})
    await log.record(event)

    assert [e.id for e in await log.pending("inbox.arrived")] == [event.id]
    assert await log.consume(event.id, NOON) is True
    assert await log.consume(event.id, NOON) is False
    assert await log.pending("inbox.arrived") == []

    kept = (await log.recent())[0]
    assert kept.consumed and kept.payload == {"from": "someone"}


async def test_deleting_a_schedule_says_whether_there_was_one(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    store = SqliteScheduleRepository(session_factory)
    created = Schedule.create("check", recurrence=Recurrence(every_seconds=3600))
    await store.save(created)

    assert await store.delete(created.id) is True
    assert await store.delete(created.id) is False
    assert await store.list() == []
