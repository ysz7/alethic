"""How the platform learns which connections exist."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.llm.catalog import ModelEntry
from domain.llm.models import TaskKind
from domain.providers.models import Connection
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId


class ConnectionRepository(Protocol):
    async def save(self, connection: Connection) -> None: ...

    async def get(self, connection_id: UUID) -> Connection | None: ...

    async def get_by_name(
        self, name: str, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> Connection | None: ...

    async def list(
        self, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> list[Connection]: ...

    async def delete(self, connection_id: UUID) -> bool: ...


class CatalogAdmin(Protocol):
    """Reading and writing the catalog a person edits.

    Narrower than the store behind it: what an application service needs is the
    entries, the defaults, and the two ways to change each. Loading a catalog
    from a file is not here, because nobody above the adapters ever does that.
    """

    async def save_entry(
        self, entry: ModelEntry, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> None: ...

    async def entries(
        self, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> list[ModelEntry]: ...

    async def delete_entry(
        self, name: str, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> bool: ...

    async def entries_using(
        self, connection: str, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> list[ModelEntry]: ...

    async def set_default(
        self,
        task_kind: TaskKind,
        entry_name: str,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> None: ...

    async def defaults(
        self, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> dict[TaskKind, str]: ...

    async def clear_default(self, task_kind: TaskKind) -> bool: ...


class ModelDiscovery(Protocol):
    """What a runner already has, so a person picks from a list.

    A callable rather than a class in the adapters: there is one implementation
    and it is one function, and a protocol here is what keeps the application
    service from importing it.
    """

    async def __call__(self, base_url: str) -> tuple[str, ...]: ...
