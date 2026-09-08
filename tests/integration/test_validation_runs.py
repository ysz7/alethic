"""What Phase 11 writes down, against a real SQLite file.

One table, and the reason it is stored at all is that every word of the phase's
Definition of Done - reliably, sometimes, not at all - is a claim about a series
of runs. A series does not survive in a terminal.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.validation.evidence import CheckResult, CheckStatus, Metrics
from domain.validation.failures import FailureKind
from domain.validation.reliability import Verdict, reliability_of
from domain.validation.run import RunStatus, ValidationRun
from infrastructure.persistence.validation_run_repository import (
    SqliteValidationRunRepository,
)


def run(scenario: str = "sort-a-folder", **extra) -> ValidationRun:
    return ValidationRun.create(
        scenario,
        extra.pop("status", RunStatus.PASSED),
        **extra,
    )


async def test_a_run_survives_the_process_that_recorded_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    runs = SqliteValidationRunRepository(session_factory)
    recorded = run(
        failure=FailureKind.NONE,
        summary="Five files filed, index written.",
        checks=(
            CheckResult("finished", CheckStatus.PASSED),
            CheckResult("file 'sorted/INDEX.md'", CheckStatus.FAILED, "not written"),
        ),
        metrics=Metrics(steps=11, cost_usd=0.0312, tool_calls=14, interventions=1),
    )
    await runs.save(recorded)

    [stored] = await runs.recent()
    assert stored.id == recorded.id
    assert stored.summary == recorded.summary
    assert stored.metrics.steps == 11
    assert stored.metrics.cost_usd == 0.0312
    assert stored.metrics.interventions == 1
    assert [check.status for check in stored.checks] == [
        CheckStatus.PASSED,
        CheckStatus.FAILED,
    ]
    assert stored.failed_checks[0].detail == "not written"


async def test_a_note_a_person_added_is_kept(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The one field no model writes, and usually the only one worth reading."""
    runs = SqliteValidationRunRepository(session_factory)
    recorded = run(status=RunStatus.FAILED, failure=FailureKind.MODEL)
    await runs.save(recorded)
    await runs.save(recorded.with_note("It wrote a closing message instead of the file."))

    [stored] = await runs.recent()
    assert stored.note.startswith("It wrote a closing message")
    assert stored.status is RunStatus.FAILED  # updated in place, not duplicated


async def test_the_history_of_one_scenario_reads_back_as_a_verdict(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    runs = SqliteValidationRunRepository(session_factory)
    now = datetime.now(UTC)
    for index, status in enumerate(
        (RunStatus.FAILED, RunStatus.PASSED, RunStatus.PASSED)
    ):
        await runs.save(
            run(
                status=status,
                failure=FailureKind.TOOL if status is RunStatus.FAILED else FailureKind.NONE,
                metrics=Metrics(steps=10 + index),
                started_at=now - timedelta(minutes=10 - index),
            )
        )
    await runs.save(run("something-else", status=RunStatus.PASSED))

    history = await runs.recent()
    assert len(history) == 4
    assert [stored.scenario for stored in await runs.recent(scenario="sort-a-folder")] == [
        "sort-a-folder"
    ] * 3

    entry = reliability_of("sort-a-folder", history)
    assert entry.verdict is Verdict.SOMETIMES  # it has passed and it has failed
    assert entry.common_failure is FailureKind.TOOL
    assert entry.median_steps == 11


async def test_a_run_recorded_under_a_category_this_build_forgot_is_still_evidence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Reading is lenient on purpose: losing history to a rename would be the
    storage layer editing the record of what happened."""
    runs = SqliteValidationRunRepository(session_factory)
    await runs.save(run(status=RunStatus.FAILED, failure=FailureKind.TOOL))
    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(text("UPDATE validation_runs SET failure = 'GREMLINS'"))
        await session.commit()

    [stored] = await runs.recent()
    assert stored.failure is FailureKind.UNKNOWN
    assert stored.status is RunStatus.FAILED
