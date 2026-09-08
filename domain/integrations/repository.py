"""Where connected integrations are kept.

One protocol, the same shape as every other repository here, and deliberately
without a "list the tools" method: what an integration offers is a field on the
integration, written when it was last discovered. A separate table of tools
would be a second place for the same answer, and the copy an interface reads
would be the one that goes stale.

`by_name` exists because the name is what a person and an employee declaration
use - `integrations: [gmail]` - while the id is what the record uses. Resolving
one to the other is a query, not a scan every caller writes for itself.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from domain.integrations.models import Integration
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId


class IntegrationRepository(Protocol):
    async def save(self, integration: Integration) -> None: ...

    async def get(self, integration_id: UUID) -> Integration | None: ...

    async def by_name(
        self, name: str, *, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> Integration | None: ...

    async def list(
        self, *, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> list[Integration]: ...

    async def delete(self, integration_id: UUID) -> bool: ...
