"""Moving the store: copy, verify, then a separately confirmed erase (ADR 0017).

Between two SQLite files, because what is under test is the order and the
checking rather than the dialect: the same three steps run against PostgreSQL,
and a test that needed a server to assert them would be a test nobody runs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import insert, select, update

from infrastructure.persistence import transfer
from infrastructure.persistence.models import (
    Base,
    DocumentRow,
    MemoryItemRow,
    TaskRow,
    WorkspaceRow,
)
from infrastructure.persistence.session import create_engine


async def build(path: Path):
    engine = create_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine


async def fill(engine, *, title: str = "Delivery policy") -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC).replace(tzinfo=None)
    async with engine.begin() as connection:
        await connection.execute(
            insert(WorkspaceRow),
            [
                {
                    "id": "work",
                    "name": "Work",
                    "description": "",
                    "settings": {},
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )
        await connection.execute(
            insert(DocumentRow.__table__),
            [
                {
                    "id": "11111111-1111-1111-1111-111111111111",
                    "workspace_id": "work",
                    "title": title,
                    "source": "/tmp/delivery.md",
                    "media_type": "text/markdown",
                    "status": "INDEXED",
                    "checksum": "abc",
                    "size_bytes": 10,
                    "chunk_count": 1,
                    "error": "",
                    "metadata": {},
                    "created_at": now,
                    "updated_at": now,
                }
            ],
        )
        await connection.execute(
            insert(MemoryItemRow.__table__),
            [
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "workspace_id": "work",
                    "scope": "USER",
                    "kind": "SEMANTIC",
                    "content": "The user prefers: Markdown",
                    "employee_id": None,
                    "plan_id": None,
                    "task_id": None,
                    "metadata": {},
                    "importance": 0.8,
                    "created_at": now,
                    "expires_at": None,
                }
            ],
        )


@pytest.fixture
async def stores(tmp_path: Path):
    source = await build(tmp_path / "here.db")
    destination = await build(tmp_path / "there.db")
    await fill(source)
    yield source, destination
    await source.dispose()
    await destination.dispose()


async def test_everything_is_copied_and_then_checked_row_by_row(stores) -> None:
    source, destination = stores

    copied = await transfer.copy(source, destination)
    checked = await transfer.verify(source, destination)

    assert copied.copied == 3 and not copied.problems
    assert checked.verified
    async with destination.connect() as connection:
        titles = (await connection.execute(select(DocumentRow.title))).scalars().all()
    assert titles == ["Delivery policy"]


async def test_a_copy_that_did_not_arrive_intact_is_reported_not_assumed(stores) -> None:
    """The point of verifying: a copy that returned without raising is not evidence."""
    source, destination = stores
    await transfer.copy(source, destination)

    async with destination.begin() as connection:
        await connection.execute(update(DocumentRow).values(title="Something else"))

    checked = await transfer.verify(source, destination)

    assert not checked.verified
    documents = next(table for table in checked.tables if table.name == "documents")
    assert documents.source_rows == documents.destination_rows == 1
    assert documents.mismatched == 1, "counts agreeing is not the rows agreeing"


async def test_copying_twice_leaves_one_copy_of_everything(stores) -> None:
    """A move interrupted halfway and started again ends with the source's rows."""
    source, destination = stores

    await transfer.copy(source, destination)
    await transfer.copy(source, destination)

    assert (await transfer.verify(source, destination)).verified


async def test_erasing_is_a_separate_act_and_empties_only_what_it_was_given(
    stores,
) -> None:
    source, destination = stores
    await transfer.copy(source, destination)

    removed = await transfer.erase(source)

    assert sum(removed.values()) == 3
    async with source.connect() as connection:
        assert (await connection.execute(select(DocumentRow))).first() is None
    async with destination.connect() as connection:
        assert (await connection.execute(select(DocumentRow))).first() is not None


async def test_the_destination_keeps_its_schema_after_an_erase(stores) -> None:
    """Erasing empties the tables; it does not drop what the migration built."""
    source, _ = stores

    await transfer.erase(source)

    async with source.connect() as connection:
        assert (await connection.execute(select(WorkspaceRow))).all() == []


async def test_a_row_a_cascade_took_is_still_a_row_that_was_erased(stores) -> None:
    """The count a person is shown before and the one shown after are the same.

    A retry hangs off the task that failed, so erasing the tasks deletes two
    rows with one statement and `rowcount` reports one. The real move in Phase
    19 said "about to erase 195" and then "erased 193", which reads as a
    partial erase of something that cannot be undone.
    """
    source, _ = stores
    now = datetime.now(UTC).replace(tzinfo=None)
    async with source.begin() as connection:
        await connection.execute(
            insert(TaskRow.__table__),
            [
                {
                    "id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "workspace_id": "work",
                    "employee_id": None,
                    "parent_task_id": None,
                    "goal": "The one that failed",
                    "status": "FAILED",
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "aaaaaaaa-0000-0000-0000-000000000002",
                    "workspace_id": "work",
                    "employee_id": None,
                    "parent_task_id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "goal": "The retry",
                    "status": "COMPLETED",
                    "created_at": now,
                    "updated_at": now,
                },
            ],
        )
    async with source.connect() as connection:
        before = len((await connection.execute(select(TaskRow.id))).all())

    removed = await transfer.erase(source)

    assert before == 2
    assert removed["tasks"] == 2
