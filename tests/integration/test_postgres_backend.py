"""What is true only of the second backend - and skipped where there is no server.

The same rule `test_local_provider.py` follows: a test that needs something
outside this repository says so and steps aside, rather than failing a suite
whose whole promise is no network and no key.

Point `PROMETHEUS_TEST_POSTGRES_URL` at an empty database to run it:

    PROMETHEUS_TEST_POSTGRES_URL=postgresql://localhost/prometheus_test uv run pytest

Note the missing path. Since Phase 19 that variable moves the *whole* suite onto
the second dialect - `tests/conftest.py` builds `session_factory` there instead
of on a SQLite file - because thirteen repositories cannot be covered by three
hand-written tests, and the three that were here agreed with everything while
two dialect defects sat in the schema. What is left in this file is what is
about the move between backends rather than about a repository, and it uses the
same fixture as everything else: a file that drops the schema in its own
teardown takes the rest of the suite with it, which is how the first full run
of it ended.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.memory.models import MemoryItem, MemoryKind, MemoryScope
from infrastructure.memory.sql import SqlMemory
from infrastructure.persistence import transfer
from infrastructure.persistence.models import Base, TaskEventRow, TaskRow
from infrastructure.persistence.session import create_engine, create_session_factory

pytestmark = pytest.mark.skipif(
    not os.environ.get("PROMETHEUS_TEST_POSTGRES_URL", ""),
    reason="No PostgreSQL server configured (PROMETHEUS_TEST_POSTGRES_URL)",
)


async def test_a_store_moves_from_sqlite_and_arrives_verified(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """The move the CLI performs, against a real server rather than a second file."""
    source = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'here.db'}")
    async with source.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await SqlMemory(create_session_factory(source)).remember(
        MemoryItem.create(
            "Something worth keeping", scope=MemoryScope.WORKSPACE, kind=MemoryKind.SEMANTIC
        )
    )
    destination = session_factory.kw["bind"]

    await transfer.copy(source, destination)
    checked = await transfer.verify(source, destination)

    assert checked.verified
    await source.dispose()


async def test_a_moved_store_can_still_be_written_to(
    session_factory: async_sessionmaker[AsyncSession], tmp_path: Path
) -> None:
    """The sequence knows about the rows the copy brought with it.

    Four tables number their own rows, and on PostgreSQL the next number comes
    from a sequence the copy never touches. So a store that arrived verified row
    for row could not take one more row: the first task event written after the
    move asked for an id that came over from SQLite. Every scenario of the
    validation set failed on it in Phase 19, and no test could have seen it -
    they build an empty schema, where the sequence is right by accident.

    Only a real server can fail this, which is the argument for the file it is
    written in.
    """
    source = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'here.db'}")
    async with source.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(
            insert(TaskRow.__table__),
            [
                {
                    "id": "cccccccc-0000-0000-0000-000000000001",
                    "workspace_id": "default",
                    "goal": "Something that happened",
                    "status": "COMPLETED",
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                }
            ],
        )
        await connection.execute(
            insert(TaskEventRow.__table__),
            [
                {
                    "id": 1,
                    "task_id": "cccccccc-0000-0000-0000-000000000001",
                    "from_status": "CREATED",
                    "to_status": "COMPLETED",
                    "payload": None,
                    "created_at": datetime.now(UTC),
                }
            ],
        )
    destination = session_factory.kw["bind"]

    await transfer.copy(source, destination)

    async with destination.begin() as connection:
        await connection.execute(
            insert(TaskEventRow.__table__),
            [
                {
                    "task_id": "cccccccc-0000-0000-0000-000000000001",
                    "from_status": "COMPLETED",
                    "to_status": "FAILED",
                    "payload": None,
                    "created_at": datetime.now(UTC),
                }
            ],
        )
        assert await connection.scalar(select(func.count()).select_from(TaskEventRow)) == 2
    await source.dispose()
