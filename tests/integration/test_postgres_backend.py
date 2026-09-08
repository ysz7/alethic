"""The second backend, against a real server - and skipped where there is none.

The same rule `test_local_provider.py` follows: a test that needs something
outside this repository says so and steps aside, rather than failing a suite
whose whole promise is no network and no key.

Point `ALETHIC_TEST_POSTGRES_URL` at an empty database to run it:

    ALETHIC_TEST_POSTGRES_URL=postgresql://localhost/alethic_test uv run pytest \\
        tests/integration/test_postgres_backend.py

What it asserts is what the two backends have to agree about: the migrations
build the same schema, an upsert is an upsert, the text index answers, and a
move from SQLite arrives verified.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import text

from app.config.settings import normalise_database_url
from application.knowledge.service import KnowledgeService
from domain.knowledge.models import KnowledgeQuery
from domain.memory.models import MemoryItem, MemoryKind, MemoryQuery, MemoryScope
from infrastructure.knowledge.extraction import Extractors
from infrastructure.knowledge.retriever import HybridRetriever
from infrastructure.knowledge.store import SqlKnowledgeStore
from infrastructure.memory.sql import SqlMemory
from infrastructure.persistence import transfer
from infrastructure.persistence.models import Base
from infrastructure.persistence.session import create_engine, create_session_factory

URL = os.environ.get("ALETHIC_TEST_POSTGRES_URL", "")

pytestmark = pytest.mark.skipif(
    not URL, reason="No PostgreSQL server configured (ALETHIC_TEST_POSTGRES_URL)"
)


@pytest.fixture
async def postgres():
    """A clean schema, built the way the platform builds it, and taken away after."""
    engine = create_engine(normalise_database_url(URL))
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_memory_items_text ON memory_items "
            "USING GIN (to_tsvector('simple', content))",
            "CREATE INDEX IF NOT EXISTS ix_chunks_text ON chunks "
            "USING GIN (to_tsvector('simple', content))",
        ):
            await connection.execute(text(statement))
    yield engine
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_memory_is_written_updated_and_found_by_words(postgres) -> None:
    memory = SqlMemory(create_session_factory(postgres))
    item = MemoryItem.create(
        "Delivery takes three working days",
        scope=MemoryScope.WORKSPACE,
        kind=MemoryKind.SEMANTIC,
    )
    await memory.remember(item)
    await memory.remember(item)  # the upsert, on the dialect that is not SQLite

    found = await memory.recall(MemoryQuery(text="delivery"))

    assert [one.content for one in found] == ["Delivery takes three working days"]


async def test_documents_are_stored_and_retrieved(postgres, tmp_path: Path) -> None:
    store = SqlKnowledgeStore(create_session_factory(postgres))
    knowledge = KnowledgeService(store=store, extractors=Extractors(), embeddings=None)
    await knowledge.add_text("Refunds are paid within ten days.", title="Refunds")

    passages = await HybridRetriever(store).retrieve(KnowledgeQuery(text="refunds"))

    assert passages and passages[0].title == "Refunds"


async def test_a_store_moves_from_sqlite_and_arrives_verified(
    postgres, tmp_path: Path
) -> None:
    source = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'here.db'}")
    async with source.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    memory = SqlMemory(create_session_factory(source))
    await memory.remember(
        MemoryItem.create(
            "Something worth keeping", scope=MemoryScope.WORKSPACE, kind=MemoryKind.SEMANTIC
        )
    )

    await transfer.copy(source, postgres)
    checked = await transfer.verify(source, postgres)

    assert checked.verified
    await source.dispose()
