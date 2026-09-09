"""Provider connection storage. SQL does not leave this package."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.errors import StorageError, StorageNotInitializedError
from domain.providers.models import Connection
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId
from infrastructure.persistence.dialect import upsert
from infrastructure.persistence.models import ConnectionRow
from infrastructure.persistence.session import session_scope


def _to_row(connection: Connection) -> dict[str, Any]:
    return {
        "id": str(connection.id),
        "workspace_id": str(connection.workspace_id),
        "name": connection.name,
        "kind": connection.kind,
        "base_url": connection.base_url,
        "secret_name": connection.secret_name,
        "needs_credential": connection.needs_credential,
        "description": connection.description,
        "updated_at": datetime.now(UTC),
    }


def _to_connection(row: ConnectionRow) -> Connection:
    return Connection(
        id=UUID(row.id),
        name=row.name,
        kind=row.kind,
        base_url=row.base_url or "",
        secret_name=row.secret_name or "",
        needs_credential=bool(row.needs_credential),
        description=row.description or "",
        workspace_id=WorkspaceId(row.workspace_id),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlConnectionRepository:
    """Implements `domain.providers.protocols.ConnectionRepository`."""

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

    async def save(self, connection: Connection) -> None:
        values = _to_row(connection)
        async with self._session() as session:
            statement = upsert(session, ConnectionRow).values(
                **values, created_at=connection.created_at
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[ConnectionRow.id],
                    set_={
                        key: value
                        for key, value in values.items()
                        if key not in ("id", "created_at")
                    },
                )
            )

    async def get(self, connection_id: UUID) -> Connection | None:
        async with self._session() as session:
            row = await session.get(ConnectionRow, str(connection_id))
            return _to_connection(row) if row else None

    async def get_by_name(
        self, name: str, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> Connection | None:
        async with self._session() as session:
            found = await session.execute(
                select(ConnectionRow).where(
                    ConnectionRow.workspace_id == str(workspace_id),
                    ConnectionRow.name == name,
                )
            )
            row = found.scalar_one_or_none()
            return _to_connection(row) if row else None

    async def list(self, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID) -> list[Connection]:
        async with self._session() as session:
            found = await session.execute(
                select(ConnectionRow)
                .where(ConnectionRow.workspace_id == str(workspace_id))
                .order_by(ConnectionRow.name)
            )
            return [_to_connection(row) for row in found.scalars()]

    async def delete(self, connection_id: UUID) -> bool:
        async with self._session() as session:
            result = await session.execute(
                delete(ConnectionRow).where(ConnectionRow.id == str(connection_id))
            )
            return bool(result.rowcount)
