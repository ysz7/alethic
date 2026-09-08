"""Workspace storage. SQL does not leave this package.

`ensure_default` is an upsert that only ever inserts: an installation that has
renamed its first workspace keeps the name it chose, and a fresh database gets
the row the migration would have written. Reading before writing would be a race
between two processes starting at once, which on SQLite is a locked database
rather than a duplicate.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.errors import StorageError, StorageNotInitializedError
from domain.workspace.models import (
    DEFAULT_WORKSPACE_ID,
    DEFAULT_WORKSPACE_NAME,
    Workspace,
    WorkspaceId,
)
from infrastructure.persistence.dialect import upsert
from infrastructure.persistence.models import WorkspaceRow
from infrastructure.persistence.session import session_scope


def _to_row(workspace: Workspace) -> dict[str, Any]:
    return {
        "id": str(workspace.id),
        "name": workspace.name,
        "description": workspace.description,
        "file_root": workspace.file_root,
        "settings": dict(workspace.settings),
        "updated_at": datetime.now(UTC),
    }


def _to_workspace(row: WorkspaceRow) -> Workspace:
    return Workspace(
        id=WorkspaceId(row.id),
        name=row.name,
        description=row.description or "",
        file_root=row.file_root,
        settings=dict(row.settings or {}),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlWorkspaceRepository:
    """Implements `domain.workspace.repository.WorkspaceRepository`."""

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

    async def save(self, workspace: Workspace) -> None:
        values = _to_row(workspace)
        async with self._session() as session:
            statement = upsert(session, WorkspaceRow).values(
                **values, created_at=workspace.created_at
            )
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[WorkspaceRow.id],
                    set_={
                        key: value
                        for key, value in values.items()
                        if key not in ("id", "created_at")
                    },
                )
            )

    async def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        async with self._session() as session:
            row = await session.get(WorkspaceRow, str(workspace_id))
            return _to_workspace(row) if row else None

    async def list(self) -> list[Workspace]:
        async with self._session() as session:
            found = await session.execute(select(WorkspaceRow).order_by(WorkspaceRow.name))
            return [_to_workspace(row) for row in found.scalars()]

    async def delete(self, workspace_id: WorkspaceId) -> bool:
        async with self._session() as session:
            result = await session.execute(
                delete(WorkspaceRow).where(WorkspaceRow.id == str(workspace_id))
            )
            return bool(result.rowcount)

    async def ensure_default(self) -> Workspace:
        default = Workspace(id=DEFAULT_WORKSPACE_ID, name=DEFAULT_WORKSPACE_NAME)
        async with self._session() as session:
            statement = upsert(session, WorkspaceRow).values(
                **_to_row(default), created_at=default.created_at
            )
            await session.execute(
                statement.on_conflict_do_nothing(index_elements=[WorkspaceRow.id])
            )
            row = await session.get(WorkspaceRow, str(DEFAULT_WORKSPACE_ID))
            return _to_workspace(row) if row else default


class InMemoryWorkspaceRepository:
    """The same contract without a file, for tests and an in-memory container."""

    def __init__(self) -> None:
        self._items: dict[WorkspaceId, Workspace] = {}

    async def save(self, workspace: Workspace) -> None:
        self._items[workspace.id] = workspace

    async def get(self, workspace_id: WorkspaceId) -> Workspace | None:
        return self._items.get(workspace_id)

    async def list(self) -> list[Workspace]:
        return sorted(self._items.values(), key=lambda item: item.name)

    async def delete(self, workspace_id: WorkspaceId) -> bool:
        return self._items.pop(workspace_id, None) is not None

    async def ensure_default(self) -> Workspace:
        existing = self._items.get(DEFAULT_WORKSPACE_ID)
        if existing is not None:
            return existing
        default = Workspace(id=DEFAULT_WORKSPACE_ID, name=DEFAULT_WORKSPACE_NAME)
        self._items[default.id] = default
        return default
