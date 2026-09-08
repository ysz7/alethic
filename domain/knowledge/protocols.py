"""The contracts knowledge is reached through.

Four of them, and the split is the point.

`KnowledgeStore` holds documents and chunks. `Retriever` answers a question with
passages. They are separate for the reason `Memory` and `MemoryMaintenance` are:
holding the ability to search is not the ability to delete, and the retriever is
the half that goes into a run.

`EmbeddingProvider` never names a model to its caller beyond reporting which one
it is - the choice comes from the router, like every other model choice in the
platform (ADR 0003). `TextExtractor` turns a file into text and knows nothing
about chunks, vectors or storage.

The rule from Phase 9 holds here unchanged: **the index narrows, the domain
decides.** Nothing in `domain/`, `application/`, `app/` or the prompts names a
vector table, a distance metric or a library - exactly as nothing names FTS5 -
so replacing the backend stays a change of adapter (ADR 0016).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol
from uuid import UUID

from domain.knowledge.models import (
    Chunk,
    Document,
    KnowledgeQuery,
    Passage,
    Vector,
)
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId


class KnowledgeStore(Protocol):
    async def save(self, document: Document) -> None: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def list(
        self, *, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> list[Document]: ...

    async def by_checksum(
        self, checksum: str, *, workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    ) -> Document | None:
        """The same text added twice is one document, updated (§15.5)."""
        ...

    async def delete(self, document_id: UUID) -> bool:
        """Remove the document, its chunks and its vectors. Memory is untouched."""
        ...

    async def replace_chunks(self, document_id: UUID, chunks: Sequence[Chunk]) -> None:
        """Write a document's passages, dropping whatever it had before.

        One method rather than add/clear, because a re-index that cleared and
        then failed would leave a document that exists and answers nothing.
        """
        ...

    async def chunks_for(self, document_id: UUID) -> list[Chunk]: ...


class PassageIndex(Protocol):
    """What a retriever needs from a store, and nothing more.

    Two questions: what passages are here, and which ones does the text index
    think mention this. Neither names an index, a metric or a library - the
    expression syntax is the index's own business, so `matching` is handed the
    user's words - which is what keeps swapping the backend a change of adapter
    (ADR 0016).
    """

    async def candidates(
        self,
        *,
        workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID,
        document_ids: frozenset[UUID] = frozenset(),
    ) -> list[tuple[Chunk, str, str]]:
        """Every passage in the workspace, with its document's title and source."""
        ...

    async def matching(self, query_text: str, limit: int) -> dict[str, float]:
        """What the text index matched, as a fraction of its own best hit."""
        ...


class Retriever(Protocol):
    async def retrieve(self, query: KnowledgeQuery) -> list[Passage]: ...


class EmbeddingProvider(Protocol):
    @property
    def model(self) -> str:
        """Which model produced these vectors. Written onto every chunk."""
        ...

    @property
    def dimension(self) -> int: ...

    async def embed(self, texts: Sequence[str]) -> list[Vector]: ...


class TextExtractor(Protocol):
    def supports(self, path: Path, media_type: str = "") -> bool: ...

    def extract(self, path: Path, media_type: str = "") -> str:
        """The document's text, or raise. Never a summary and never truncated."""
        ...
