"""Memory on the local SQLite file. SQL does not leave this package.

The text search is FTS5, and it is the only part of the system that knows that.
It is used the way an index should be used - to narrow, not to decide: the index
answers *which items mention this*, and `domain.memory.ranking` answers *which
of those are worth reading now*. Ranking by BM25 alone would return the best
textual match to "the report", which is every report ever written.

The rank from the index is turned into a relevance between 0 and 1 rather than
passed through raw, because the domain multiplies it by importance and decay,
and a score whose scale depends on the backend would make the policy depend on
the backend too.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from re import findall
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.errors import StorageError, StorageNotInitializedError
from domain.memory.access import visible
from domain.memory.models import MemoryItem, MemoryKind, MemoryQuery, MemoryScope
from domain.memory.ranking import CUTOFF_RATIO, best_of, score
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId
from infrastructure.persistence.models import MemoryItemRow
from infrastructure.persistence.session import session_scope

#: How many index hits to score before cutting to the caller's limit. The index
#: ranks by text alone; the ranking that matters also weighs importance and age,
#: so it needs more than `limit` rows to have anything to reorder.
CANDIDATE_FACTOR = 5


def _match_expression(query_text: str) -> str:
    """The user's words as something FTS5 will accept.

    A goal is prose, and prose contains quotes, colons and hyphens - all of
    which are operators in FTS5's query language, and any one of which turns a
    search into a syntax error. So the words are extracted and quoted, and the
    query language is never handed text it could be injected through.
    """
    words = findall(r"\w+", query_text)
    return " OR ".join(f'"{word}"' for word in words if len(word) > 1)


def _to_row(item: MemoryItem) -> dict[str, object]:
    return {
        "id": str(item.id),
        "workspace_id": str(item.workspace_id),
        "scope": item.scope.value,
        "kind": item.kind.value,
        "content": item.content,
        "employee_id": str(item.employee_id) if item.employee_id else None,
        "plan_id": str(item.plan_id) if item.plan_id else None,
        "task_id": str(item.task_id) if item.task_id else None,
        "metadata": dict(item.metadata),
        "importance": float(item.importance),
        "created_at": item.created_at,
        "expires_at": item.expires_at,
    }


def _to_item(row: MemoryItemRow) -> MemoryItem:
    return MemoryItem(
        id=UUID(row.id),
        workspace_id=WorkspaceId(row.workspace_id),
        scope=MemoryScope(row.scope),
        kind=MemoryKind(row.kind),
        content=row.content,
        employee_id=UUID(row.employee_id) if row.employee_id else None,
        plan_id=UUID(row.plan_id) if row.plan_id else None,
        task_id=UUID(row.task_id) if row.task_id else None,
        metadata=row.meta or {},
        importance=row.importance,
        created_at=_aware(row.created_at),
        expires_at=_aware(row.expires_at) if row.expires_at else None,
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


class SqliteMemory:
    """Implements `domain.memory.protocols.Memory` and `MemoryMaintenance`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        try:
            async with session_scope(self._session_factory) as session:
                yield session
        except OperationalError as error:
            message = str(error.orig)
            if "no such table" in message or "unable to open database file" in message:
                raise StorageNotInitializedError(
                    "The local database has no schema yet."
                ) from error
            raise StorageError(message) from error

    async def remember(self, item: MemoryItem) -> None:
        values = _to_row(item)
        async with self._session() as session:
            # Against the table rather than the mapped class: the JSON column is
            # called `metadata`, which a declarative class cannot use as an
            # attribute name, and the insert is by column name either way.
            statement = sqlite_insert(MemoryItemRow.__table__).values(**values)
            # Upsert on the id: consolidation rewrites an item's content, and a
            # second row saying the same thing under a new id would make the
            # thing it replaced un-findable rather than replaced.
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[MemoryItemRow.__table__.c.id],
                    set_={k: v for k, v in values.items() if k not in ("id", "created_at")},
                )
            )

    async def recall(self, query: MemoryQuery) -> list[MemoryItem]:
        if not query.scopes or query.limit <= 0:
            return []
        now = query.as_of or datetime.now(UTC)
        async with self._session() as session:
            ranked = await self._matching(session, query)
            if ranked is not None and not ranked:
                return []  # the search ran and nothing mentioned it

            statement = select(MemoryItemRow).where(
                MemoryItemRow.workspace_id == str(query.workspace_id),
                MemoryItemRow.scope.in_([scope.value for scope in query.scopes]),
            )
            if query.kinds:
                statement = statement.where(
                    MemoryItemRow.kind.in_([kind.value for kind in query.kinds])
                )
            if ranked is not None:
                statement = statement.where(MemoryItemRow.id.in_(list(ranked)))
            rows = await session.scalars(
                statement.order_by(MemoryItemRow.created_at.desc()).limit(
                    max(query.limit * CANDIDATE_FACTOR, query.limit)
                )
            )
            candidates = [_to_item(row) for row in rows]

        # The SQL narrowed; the access rule decides. Applying it here as well
        # means an index that has drifted returns fewer rows, never another
        # employee's (see `domain/memory/access.py`).
        scored = [
            (score(item, relevance=(ranked or {}).get(str(item.id), 1.0), now=now), item)
            for item in candidates
            if visible(item, query)
        ]
        # A search is ranked and cut; a listing is only ranked. See `best_of`.
        cutoff = CUTOFF_RATIO if ranked is not None else 0.0
        return best_of(scored, query.limit, cutoff=cutoff)

    async def forget(self, ids: Sequence[UUID]) -> int:
        if not ids:
            return 0
        async with self._session() as session:
            result = await session.execute(
                delete(MemoryItemRow).where(MemoryItemRow.id.in_([str(i) for i in ids]))
            )
            return int(result.rowcount or 0)

    async def prune(
        self,
        *,
        now: datetime | None = None,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> int:
        moment = now or datetime.now(UTC)
        async with self._session() as session:
            result = await session.execute(
                delete(MemoryItemRow).where(
                    MemoryItemRow.workspace_id == str(workspace_id),
                    MemoryItemRow.expires_at.is_not(None),
                    MemoryItemRow.expires_at <= moment,
                )
            )
            return int(result.rowcount or 0)

    # --- The index ------------------------------------------------------------

    async def _matching(
        self, session: AsyncSession, query: MemoryQuery
    ) -> dict[str, float] | None:
        """Item ids the text index matched, and how strongly.

        `None` means no text was asked for, which is a listing rather than a
        search and must not be confused with a search that found nothing.
        """
        expression = _match_expression(query.text)
        if not expression:
            return None
        rows = await session.execute(
            text(
                "SELECT item_id, rank FROM memory_items_fts "
                "WHERE memory_items_fts MATCH :expression "
                "ORDER BY rank LIMIT :limit"
            ),
            {"expression": expression, "limit": max(query.limit * CANDIDATE_FACTOR, 20)},
        )
        hits = rows.all()
        if not hits:
            return {}
        # FTS5's rank is negative and unbounded below, better meaning smaller.
        # Expressed as a fraction of the best hit, so a result half as good as
        # the best scores half as much whatever the absolute numbers are - and
        # the domain's cutoff means the same thing on every backend.
        best = min(float(rank) for _, rank in hits)
        return {
            str(item_id): min(max(float(rank) / best, 0.0), 1.0) if best else 1.0
            for item_id, rank in hits
        }
