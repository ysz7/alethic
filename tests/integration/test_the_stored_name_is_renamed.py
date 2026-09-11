"""Migration 022, against a database that was written before it.

A fresh schema proves nothing here: it has no rows carrying the old name and
its CHECK constraint was built from the new enum. What has to work is a
database that lived through the old name - migrated to 021, holding the values
the manager wrote then - being carried to head, after which the old values are
gone and the constraint takes the new one and refuses the old.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]


def _alembic(database: Path) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    migrations = REPO_ROOT / "infrastructure" / "persistence" / "migrations"
    config.set_main_option("script_location", str(migrations))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database}")
    return config


def _insert(connection: sqlite3.Connection, table: str, **values: object) -> None:
    """A row with the given values and something plausible in every other required column."""
    filler = {"INTEGER": 0, "REAL": 0.0, "FLOAT": 0.0, "BOOLEAN": 1}
    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
    for _, name, kind, notnull, default, primary in columns:
        if name in values or not notnull or default is not None:
            continue
        if primary and kind == "INTEGER":
            continue
        kind = kind.upper()
        moment = "DATE" in kind or "TIME" in kind
        values[name] = filler.get(kind.split("(")[0], "2026-09-10 00:00:00" if moment else "x")
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(values.values()))


@pytest.fixture
def lived_through_the_old_name(tmp_path: Path) -> Path:
    database = tmp_path / "before.db"
    command.upgrade(_alembic(database), "021")
    with sqlite3.connect(database) as connection:
        _insert(connection, "tasks", id="t1", goal="g", status="COMPLETED", created_by="alethic")
        _insert(
            connection,
            "task_assignments",
            id="a1",
            task_id="t1",
            assigned_by="ALETHIC",
            assigned_by_id="alethic",
        )
        _insert(connection, "audit_log", actor_kind="ALETHIC", actor_id="alethic", result="SUCCESS")
    return database


def test_the_rows_carry_the_new_name(lived_through_the_old_name: Path) -> None:
    command.upgrade(_alembic(lived_through_the_old_name), "head")

    with sqlite3.connect(lived_through_the_old_name) as connection:
        assert connection.execute("SELECT created_by FROM tasks").fetchall() == [("prometheus",)]
        assert connection.execute(
            "SELECT assigned_by, assigned_by_id FROM task_assignments"
        ).fetchall() == [("PROMETHEUS", "prometheus")]
        assert connection.execute("SELECT actor_kind, actor_id FROM audit_log").fetchall() == [
            ("PROMETHEUS", "prometheus")
        ]


def test_the_constraint_takes_the_new_name_and_refuses_the_old(
    lived_through_the_old_name: Path,
) -> None:
    command.upgrade(_alembic(lived_through_the_old_name), "head")

    with sqlite3.connect(lived_through_the_old_name) as connection:
        _insert(connection, "audit_log", actor_kind="PROMETHEUS", result="SUCCESS")
        with pytest.raises(sqlite3.IntegrityError):
            _insert(connection, "audit_log", actor_kind="ALETHIC", result="SUCCESS")


def test_going_back_restores_the_old_name(lived_through_the_old_name: Path) -> None:
    config = _alembic(lived_through_the_old_name)
    command.upgrade(config, "head")
    command.downgrade(config, "021")

    with sqlite3.connect(lived_through_the_old_name) as connection:
        assert connection.execute("SELECT actor_kind FROM audit_log").fetchall() == [("ALETHIC",)]
        assert connection.execute("SELECT created_by FROM tasks").fetchall() == [("alethic",)]
