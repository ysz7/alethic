"""Migration 001 must produce exactly the schema the models declare."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from infrastructure.persistence.models import Base

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option(
        "script_location", str(REPO_ROOT / "infrastructure/persistence/migrations")
    )
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_the_history_is_a_single_line() -> None:
    """Branching migrations on a one-file local database buy nothing but pain."""
    script = ScriptDirectory.from_config(_alembic_config("sqlite://"))
    assert len(script.get_heads()) == 1


def test_migration_creates_the_declared_tables(tmp_path: Path) -> None:
    from alembic import command

    database = tmp_path / "migrated.db"
    command.upgrade(_alembic_config(f"sqlite+aiosqlite:///{database}"), "head")

    inspector = inspect(create_engine(f"sqlite:///{database}"))
    # The two text indexes - one over memory, one over document passages - and
    # the shadow tables SQLite creates for them are declared as DDL rather than
    # as metadata, because a virtual table has no columns to compare. They are
    # excluded here and checked by exercising a search instead
    # (tests/integration/test_memory_repository.py, tests/unit/test_knowledge.py).
    indexes = ("memory_items_fts", "chunks_fts")
    tables = {
        name
        for name in inspector.get_table_names()
        if name != "alembic_version" and not name.startswith(indexes)
    }
    assert tables == set(Base.metadata.tables)

    for name, table in Base.metadata.tables.items():
        migrated = {column["name"] for column in inspector.get_columns(name)}
        assert migrated == set(table.columns.keys()), f"column drift in {name}"
