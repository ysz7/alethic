"""The connections this process can build a client from, held for lookup.

`ProviderFactory.for_choice` is synchronous and stays that way: it runs at the
moment a model is called, and an await there would put a database round trip on
the hot path of every request. So the rows are loaded once at start-up - the
same `restore` shape the credentials and the integrations use, and for the same
reason - and looked up by name afterwards.

What it holds is the record, never a credential: the record names a secret and
the factory resolves it at the moment of the call.
"""

from __future__ import annotations

import structlog

from domain.providers.models import Connection
from domain.providers.protocols import ConnectionRepository
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId

log = structlog.get_logger(__name__)


class ConnectionDirectory:
    """Names to connections. Empty until restored, which is a working state."""

    def __init__(
        self,
        repository: ConnectionRepository | None = None,
        *,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> None:
        self._repository = repository
        self._workspace_id = workspace_id
        self._by_name: dict[str, Connection] = {}

    def get(self, name: str) -> Connection | None:
        return self._by_name.get(name)

    def all(self) -> tuple[Connection, ...]:
        return tuple(self._by_name.values())

    def remember(self, connection: Connection) -> None:
        """Take a change without a round trip, so a page reflects what it saved."""
        self._by_name[connection.name] = connection

    def forget(self, name: str) -> None:
        self._by_name.pop(name, None)

    async def restore(self) -> None:
        if self._repository is None:
            return
        stored = await self._repository.list(self._workspace_id)
        self._by_name = {connection.name: connection for connection in stored}
        log.info("connections.restored", count=len(self._by_name))
