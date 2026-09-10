"""Moving the store from one backend to another: copy, verify, then erase.

"After moving to B the data is not left on A" is the right goal and has exactly
one safe order, and this module is that order (ADR 0017).

**Copy is not the move.** It creates the schema on the destination by running
the migrations there - not by copying DDL, because the two backends do not have
the same DDL - and then copies every table in dependency order. It is
idempotent per row: a rerun after a failure updates what is already there rather
than duplicating it.

**Verification reads the destination.** Counts per table and then the rows
themselves, compared by primary key, because a copy that returned without
raising is not evidence that anything arrived - the same rule the validation
harness follows when it checks the store rather than the summary a run produced
(ADR 0011).

**Erasing is separate and says what it will destroy.** It is irreversible, and
irreversible things in this platform wait for a person (ADR 0004). The state in
between - on B and still on A - is not a defect: it is the point at which the
move can still be abandoned.

**Two things do not travel.** The credential file is a file on this machine and
stays one (§74). The text index is rebuilt rather than copied, because FTS5 and
`tsvector` are different things - which is why the destination's schema is
created by its own migrations instead of being carried across.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import delete, func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from infrastructure.observability.logging import get_logger
from infrastructure.persistence.dialect import POSTGRES, advance_identity
from infrastructure.persistence.models import Base

log = get_logger(__name__)

#: How many rows are read and written at a time. Large enough that a move of a
#: hundred thousand rows is not a hundred thousand round trips, small enough
#: that a table nobody expected to be large does not have to fit in memory.
BATCH = 500


@dataclass(frozen=True, slots=True)
class TableResult:
    name: str
    copied: int = 0
    source_rows: int = 0
    destination_rows: int = 0
    mismatched: int = 0

    @property
    def verified(self) -> bool:
        return self.source_rows == self.destination_rows and not self.mismatched


@dataclass(frozen=True, slots=True)
class TransferResult:
    tables: tuple[TableResult, ...] = ()
    problems: tuple[str, ...] = field(default_factory=tuple)

    @property
    def copied(self) -> int:
        return sum(table.copied for table in self.tables)

    @property
    def verified(self) -> bool:
        """Every table agrees, and nothing went wrong on the way."""
        return not self.problems and all(table.verified for table in self.tables)


def _tables():
    """Every table, parents before children, so a foreign key is never dangling."""
    return list(Base.metadata.sorted_tables)


async def row_counts(engine: AsyncEngine) -> dict[str, int]:
    """How many rows each table holds, read off the schema rather than a list.

    Here rather than in the command that prints it, because SQL does not leave
    this package - the same rule that keeps every repository's queries in it.
    """
    counts: dict[str, int] = {}
    async with engine.connect() as connection:
        for table in _tables():
            counts[table.name] = int(
                await connection.scalar(select(func.count()).select_from(table)) or 0
            )
    return counts


async def copy(source: AsyncEngine, destination: AsyncEngine) -> TransferResult:
    """Copy every row from one store to the other. The schema must already exist.

    Existing rows on the destination are overwritten by primary key rather than
    skipped: a move interrupted halfway and started again should end with the
    source's version of every row, not with whichever arrived first.
    """
    results: list[TableResult] = []
    problems: list[str] = []
    for table in _tables():
        copied = 0
        try:
            async with source.connect() as reader:
                rows = await reader.stream(select(table))
                async for batch in rows.partitions(BATCH):
                    payload = [dict(row._mapping) for row in batch]
                    if not payload:
                        continue
                    async with destination.begin() as writer:
                        keys = list(table.primary_key.columns)
                        if keys:
                            await writer.execute(
                                delete(table).where(
                                    keys[0].in_([row[keys[0].name] for row in payload])
                                )
                                if len(keys) == 1
                                else delete(table)
                            )
                        await writer.execute(insert(table), payload)
                    copied += len(payload)
        except Exception as error:  # a backend failure is a report, not a traceback
            problems.append(f"{table.name}: {error}")
            log.warning("storage.copy_failed", table=table.name, error=str(error))
        results.append(TableResult(name=table.name, copied=copied))
        log.info("storage.copied", table=table.name, rows=copied)
    problems.extend(await _advance_identities(destination))
    return TransferResult(tables=tuple(results), problems=tuple(problems))


async def _advance_identities(destination: AsyncEngine) -> list[str]:
    """Part of the copy, not a tidy-up after it.

    Four tables number their own rows. The copy brings the numbers with it and
    says nothing to the sequence that hands out the next one, so a store moved
    onto PostgreSQL verified row for row and then could not write: the first
    task event after the move asked for id 1, which had arrived from SQLite an
    hour earlier. Every recorded run of the validation set failed on it, and
    nothing in the suite could see it - a test builds an empty schema and
    inserts, which is the one case where the sequence is already right.

    A problem here is a problem with the move, and the move reports problems
    rather than raising: the caller is a person watching a copy it can still
    abandon.
    """
    if destination.dialect.name != POSTGRES:
        # SQLite takes the next id from the highest one present, so the rows
        # that arrived have already said everything there is to say.
        return []
    problems: list[str] = []
    async with destination.begin() as connection:
        for table in _tables():
            column = table.autoincrement_column
            if column is None:
                continue
            try:
                await connection.execute(text(advance_identity(table.name, column.name)))
            except Exception as error:
                problems.append(f"{table.name}.{column.name}: {error}")
                log.warning(
                    "storage.identity_not_advanced", table=table.name, error=str(error)
                )
    return problems


async def verify(source: AsyncEngine, destination: AsyncEngine) -> TransferResult:
    """Compare the two stores table by table, and then row by row.

    Counts first because a missing table is worth saying plainly, then the rows
    themselves by primary key: a count that matches while the contents differ is
    exactly the failure a count-only check would call success.
    """
    results: list[TableResult] = []
    problems: list[str] = []
    for table in _tables():
        try:
            async with source.connect() as reader, destination.connect() as checker:
                here = await reader.scalar(select(func.count()).select_from(table))
                there = await checker.scalar(select(func.count()).select_from(table))
                mismatched = await _mismatched(reader, checker, table)
        except Exception as error:
            problems.append(f"{table.name}: {error}")
            results.append(TableResult(name=table.name))
            continue
        results.append(
            TableResult(
                name=table.name,
                source_rows=int(here or 0),
                destination_rows=int(there or 0),
                mismatched=mismatched,
            )
        )
    return TransferResult(tables=tuple(results), problems=tuple(problems))


async def _mismatched(reader, checker, table) -> int:
    """How many of the source's rows are missing or different on the destination."""
    keys = list(table.primary_key.columns)
    if not keys:
        return 0
    key = keys[0]
    wrong = 0
    rows = await reader.stream(select(table))
    async for batch in rows.partitions(BATCH):
        mine = {row._mapping[key.name]: dict(row._mapping) for row in batch}
        found = await checker.execute(select(table).where(key.in_(list(mine))))
        theirs = {row._mapping[key.name]: dict(row._mapping) for row in found}
        for identifier, row in mine.items():
            other = theirs.get(identifier)
            if other is None or not _same(row, other):
                wrong += 1
    return wrong


def _same(left: dict, right: dict) -> bool:
    """Whether two copies of a row say the same thing.

    Compared through `str` for the values the two backends represent
    differently - a datetime that arrives with a timezone on one and without on
    the other, a JSON column that comes back as text on one and as a dict on the
    other. What is being verified is that the data arrived, not that two drivers
    agree on a Python type.
    """
    if set(left) != set(right):
        return False
    return all(_comparable(left[key]) == _comparable(right[key]) for key in left)


def _comparable(value):
    if value is None or isinstance(value, (int, float, bool, bytes)):
        return value
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value, sort_keys=True, default=str)
    return str(value).replace("+00:00", "").strip()


async def erase(engine: AsyncEngine) -> dict[str, int]:
    """Empty every table, children before parents. Irreversible, by design.

    Deliberately not "drop the database": the schema is what a migration built
    and what the platform will look for the next time it starts. What is being
    destroyed is the data, and the caller has already told a person exactly how
    much of it there is.
    """
    removed: dict[str, int] = {}
    async with engine.begin() as connection:
        for table in reversed(_tables()):
            # Counted before the delete rather than taken from `rowcount`, which
            # sees only the rows this statement removed itself. A retry hangs off
            # the task that failed, so deleting the parents took two child tasks
            # with it by cascade, and the erase reported 193 rows one line after
            # telling a person it was about to erase 195. Two numbers that
            # disagree about an irreversible act read as a partial erase, and
            # twenty-five counts is a cheap price for the one that is true.
            present = await connection.execute(select(func.count()).select_from(table))
            await connection.execute(delete(table))
            removed[table.name] = int(present.scalar() or 0)
    log.warning("storage.erased", tables=len(removed), rows=sum(removed.values()))
    return removed
