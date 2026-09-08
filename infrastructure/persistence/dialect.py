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

**Full-text search.** SQLite has FTS5 and PostgreSQL has `tsvector`, and they
are different enough that the query is written twice rather than abstracted into
something that is neither. Both return the same thing to the domain: ids and a
rank normalised to a fraction of the best hit, which is what makes the two
comparable (ADR 0016).

Vectors are deliberately *not* here. They are bytes on both, compared in memory,
because at one person's scale that costs milliseconds and needs no extension -
ADR 0017 says when that stops being true and what to do about it then.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

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
