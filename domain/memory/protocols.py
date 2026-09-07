"""The contracts memory is reached through, and the reason there are two.

`Memory` is what everything above uses: two methods, and `recall` is the only
way anything is ever searched for. No caller anywhere states a table, a query
language or an index - which is what keeps the backend replaceable, and is the
one rule this phase is built around (§9.9).

`MemoryMaintenance` is separate because it answers a different question and has
a different audience. Reading and writing happen inside a run; forgetting is
housekeeping, done by whoever is allowed to decide that something has stopped
being worth keeping. Folding both into one interface would hand every caller of
`recall` the ability to delete.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.memory.models import MemoryItem, MemoryQuery
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId


class Memory(Protocol):
    """The only way into memory. Search never bypasses `recall`."""

    async def remember(self, item: MemoryItem) -> None: ...

    async def recall(self, query: MemoryQuery) -> list[MemoryItem]: ...


class MemoryMaintenance(Protocol):
    """Keeping memory from growing without bound."""

    async def forget(self, ids: Sequence[UUID]) -> int:
        """Drop these items. Used when several have been folded into one."""
        ...

    async def prune(
        self,
        *,
        now: datetime | None = None,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
    ) -> int:
        """Drop what has passed its time to live. Returns how many went."""
        ...
