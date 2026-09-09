"""The catalog, assembled from what is stored and seeded from what ships.

Three rules, and each rejects an alternative that looked simpler.

**A named path wins outright.** `ALETHIC_MODEL_CATALOG_PATH` is how validation
and CI say which models to use, in one environment variable and without a
database somebody would have to populate first. When it is set, the file is the
catalog and the store is not consulted - not merged with, not overridden by.
Merging would mean a run whose models depend on rows nobody looking at the
command line can see.

**Otherwise the store wins, seeded once from the shipped file.** A fresh
installation gets the entries the developers chose and then owns them: an entry
edited in the window must not come back on the next start, which is what
re-seeding every time would do. `is_empty` is what "once" means, and it is a
property of the installation rather than a flag somebody has to remember to set.

**A default pointing at an entry that is gone is dropped, not obeyed.** The
router treats a default as the winner among candidates, so a dangling one would
route every task of that kind to an error. Dropping it falls back to ranking by
hints, which is what a machine with no default does anyway.

**An entry nothing can reach is not a candidate.** Found by the Phase 17
validation run: a machine with a local provider connected and every kind of work
routed to it still sent one call to a shipped hosted entry and got a 401, because
the quality floor on verification filtered out the routed entry and the hints
then ranked a model with no key behind it. The entry is not deleted - it is the
user's row and it stays in Settings where they can see and remove it - but a
model the platform cannot call is not something to route work to.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import structlog

from domain.llm.catalog import ModelEntry
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId
from infrastructure.llm.catalog import ModelCatalog
from infrastructure.persistence.catalog_repository import SqlCatalogRepository

log = structlog.get_logger(__name__)


class StoredCatalogSource:
    """Where `Container.model_catalog` gets its entries once storage is up."""

    def __init__(
        self,
        repository: SqlCatalogRepository,
        *,
        configured_path: Path | None = None,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
        reachable: Callable[[ModelEntry], bool] | None = None,
    ) -> None:
        self._repository = repository
        self._configured_path = configured_path
        self._workspace_id = workspace_id
        # Answered by the composition root, which is the only thing that knows
        # both what was configured and what was connected. None means "assume
        # everything is reachable", which is what a file-only catalog means.
        self._reachable = reachable

    @property
    def is_overridden(self) -> bool:
        """Whether a file was named, in which case nothing here applies."""
        return self._configured_path is not None

    async def load(self) -> ModelCatalog:
        """The catalog this installation should use, seeding on the first run."""
        if self._configured_path is not None:
            return ModelCatalog.load(self._configured_path)

        if await self._repository.is_empty(self._workspace_id):
            await self._seed()

        stored = await self._repository.entries(self._workspace_id)
        entries = tuple(entry for entry in stored if self._can_reach(entry))
        if len(entries) != len(stored):
            log.info(
                "catalog.unreachable_entries",
                names=[e.name for e in stored if e not in entries],
            )
        known = {entry.name for entry in entries}
        defaults = {
            kind: name
            for kind, name in (await self._repository.defaults(self._workspace_id)).items()
            if name in known
        }
        log.info("catalog.loaded", entries=len(entries), defaults=len(defaults))
        return ModelCatalog(entries=entries, defaults=defaults)

    async def _seed(self) -> None:
        """Copy the shipped file in. Runs once per installation, by definition."""
        shipped = ModelCatalog.load()
        for entry in shipped.entries:
            await self._repository.save_entry(entry, self._workspace_id)
        for kind, name in shipped.defaults.items():
            await self._repository.set_default(kind, name, self._workspace_id)
        log.info("catalog.seeded", entries=len(shipped.entries))

    def _can_reach(self, entry: ModelEntry) -> bool:
        return self._reachable is None or self._reachable(entry)
