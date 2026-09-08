"""Where workspaces are kept.

The same shape as every other repository here, with one method that is not on
the others: `ensure_default`. A machine that has been running since Phase 1 has
rows in thirteen tables belonging to a workspace whose record does not exist
yet, and the first read must not be the one that discovers it. The default row
is written by the migration and asserted here, so a database built by
`create_all` - which is what the test suite does - holds it too.

There is deliberately no `active` method. Which workspace is active is a
setting of this installation, not a column: two processes on one machine may be
working in different ones, and a row saying which is "the" active workspace
would make the second one wrong.
"""

from __future__ import annotations

from typing import Protocol

from domain.workspace.models import Workspace, WorkspaceId


class WorkspaceRepository(Protocol):
    async def save(self, workspace: Workspace) -> None: ...

    async def get(self, workspace_id: WorkspaceId) -> Workspace | None: ...

    async def list(self) -> list[Workspace]: ...

    async def delete(self, workspace_id: WorkspaceId) -> bool: ...

    async def ensure_default(self) -> Workspace: ...
