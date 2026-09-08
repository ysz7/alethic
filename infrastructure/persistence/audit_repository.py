"""Audit storage. SQL does not leave this package.

The one behaviour worth stating: `record` never raises at its caller. An audit
line is written on the path of every tool call, and a database that has gone
away must not be able to stop work that was already approved. The failure is
logged and the action proceeds - the alternative is a platform that stops
working when its accountant does, which nobody would choose if asked.

Note that this is the *adapter's* guarantee, and the callers guard too. Both,
deliberately: the caller cannot know what a given implementation throws, and an
implementation cannot know it is the only one being called.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.audit.protocols import AuditRecord
from domain.errors import StorageError, StorageNotInitializedError
from domain.policies.models import ActorKind
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.models import AuditRow
from infrastructure.persistence.session import session_scope

log = get_logger(__name__)


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _to_record(row: AuditRow) -> AuditRecord:
    return AuditRecord(
        action=row.action,
        actor_kind=ActorKind(row.actor_kind),
        result=row.result,
        actor_id=row.actor_id,
        workspace_id=WorkspaceId(row.workspace_id),
        task_id=UUID(row.task_id) if row.task_id else None,
        assignment_id=UUID(row.assignment_id) if row.assignment_id else None,
        tool=row.tool,
        model=row.model,
        cost_usd=row.cost_usd,
        latency_ms=row.latency_ms,
        details=row.details or {},
        timestamp=_aware(row.ts),
    )


class SqlAuditLog:
    """Implements `domain.audit.protocols.AuditLog` and `AuditTrail`."""

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
                raise StorageNotInitializedError("The local database has no schema yet.") from error
            raise StorageError(message) from error

    async def record(self, record: AuditRecord) -> None:
        try:
            async with self._session() as session:
                session.add(
                    AuditRow(
                        ts=record.timestamp,
                        workspace_id=str(record.workspace_id),
                        actor_kind=record.actor_kind.value,
                        actor_id=record.actor_id,
                        task_id=str(record.task_id) if record.task_id else None,
                        assignment_id=(
                            str(record.assignment_id) if record.assignment_id else None
                        ),
                        action=record.action,
                        tool=record.tool,
                        model=record.model,
                        result=record.result,
                        cost_usd=record.cost_usd,
                        latency_ms=record.latency_ms,
                        details=dict(record.details),
                    )
                )
        except (SQLAlchemyError, StorageError, StorageNotInitializedError) as error:
            log.warning("audit.not_recorded", action=record.action, error=str(error))

    async def recent(
        self,
        *,
        limit: int = 50,
        task_id: UUID | None = None,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> list[AuditRecord]:
        async with self._session() as session:
            statement = (
                select(AuditRow)
                .where(AuditRow.workspace_id == str(workspace_id))
                .order_by(AuditRow.ts.desc(), AuditRow.id.desc())
                .limit(limit)
            )
            if task_id is not None:
                statement = statement.where(AuditRow.task_id == str(task_id))
            rows = await session.scalars(statement)
            return [_to_record(row) for row in rows]


class InMemoryAuditLog:
    """Implements the same two protocols, for tests and for a run with no store."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)

    async def recent(
        self,
        *,
        limit: int = 50,
        task_id: UUID | None = None,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> list[AuditRecord]:
        matching = [
            record
            for record in self.records
            if record.workspace_id == workspace_id
            and (task_id is None or record.task_id == task_id)
        ]
        return sorted(matching, key=lambda r: r.timestamp, reverse=True)[:limit]
