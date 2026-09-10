"""What differs between one SQL backend and another, in one place.

Since Phase 15 there are two: SQLite, which is what `clone && run` gets, and
PostgreSQL, which is what somebody who already runs a server can point at
(ADR 0017). They are one set of adapters rather than two, because two
implementations of thirteen repositories would be two things to keep true and
one of them would quietly fall behind.

What actually differs is small and is all here.

**The upsert.** Both dialects have `ON CONFLICT DO UPDATE` and both express it
through a dialect-specific `insert()`; the construct is chosen from the session's
own bind, so a repository writes one statement and neither dialect is named
above this module.

**A timestamp.** The domain works in aware UTC (`datetime.now(UTC)`) and the
column is naive, because that is what both dialects were given by migration
001. SQLite did not mind - it stores a string and hands one back - so the
conversion existed on the read side only, in a `_aware` helper each repository
kept for itself, and the write side worked by accident. PostgreSQL refuses an
aware value for `TIMESTAMP WITHOUT TIME ZONE` outright, which is how Phase 19
found it. `UtcTimestamp` does both halves once, on the column type, rather than
in the thirteen repositories that would each have to remember: what goes in is
converted to UTC and stripped, what comes out is UTC again. Widening the column
to `timestamptz` was the alternative - it would have been a migration over every
timestamp in the schema to store what is already always UTC.

**Full-text search.** SQLite has FTS5 and PostgreSQL has `tsvector`, and they
are different enough that the query is written twice rather than abstracted into
something that is neither. Both return the same thing to the domain: ids and a
rank normalised to a fraction of the best hit, which is what makes the two
comparable (ADR 0016).

**A copied identity column.** Four tables number their own rows, and on
PostgreSQL that number comes from a sequence rather than from the column. A
copy inserts the ids it was given and never touches the sequence, so a store
moved onto PostgreSQL had every one of them still sitting at 1: the first task
event written after the move collided with a row that came from SQLite, and so
did the next twenty-three. `advance_identity` is the statement that fixes it,
and it is only PostgreSQL's problem - SQLite takes the next id from the highest
one present, which is the same answer arrived at without being told.

Vectors are deliberately *not* here. They are bytes on both, compared in memory,
because at one person's scale that costs milliseconds and needs no extension -
ADR 0017 says when that stops being true and what to do about it then.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import TypeDecorator

POSTGRES = "postgresql"
SQLITE = "sqlite"


def dialect_of(session: AsyncSession) -> str:
    """Which backend this session is talking to, asked rather than configured."""
    bind = session.get_bind()
    return bind.dialect.name


def upsert(session: AsyncSession, target: Any):
    """An INSERT that can be given an ON CONFLICT clause, for this session's backend.

    The two dialects' constructs take the same arguments for what this codebase
    does with them - `index_elements`, `set_` - so callers write the clause once.
    """
    return postgres_insert(target) if dialect_of(session) == POSTGRES else sqlite_insert(target)


def is_postgres(session: AsyncSession) -> bool:
    return dialect_of(session) == POSTGRES


class UtcTimestamp(TypeDecorator):
    """A naive UTC column that the rest of the platform sees as aware UTC.

    A naive value on the way in is taken to be UTC already rather than raising:
    it is what SQLite has been handing back since Phase 1, and a store that
    cannot read its own history is worse than one that assumes the timezone
    every writer in this codebase actually uses.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


def advance_identity(table: str, column: str) -> str:
    """Tell PostgreSQL's sequence for `table.column` about the rows that arrived.

    `pg_get_serial_sequence` returns NULL where there is no sequence and `setval`
    is strict, so a table this is asked about wrongly is a no-op rather than an
    error - which is what a statement run over the whole schema needs to be.
    """
    return (
        f"SELECT setval(pg_get_serial_sequence('{table}', '{column}'), "
        f"coalesce((SELECT max({column}) FROM {table}), 0) + 1, false)"
    )
