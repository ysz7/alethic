"""Workspaces: the record, the switch, and the root that follows it."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.workspaces.service import WorkspaceService
from domain.errors import (
    DuplicateWorkspaceError,
    ProtectedWorkspaceError,
    WorkspaceNotFoundError,
)
from domain.workspace.models import DEFAULT_WORKSPACE_ID, Workspace, WorkspaceId, slug
from infrastructure.persistence.workspace_repository import (
    InMemoryWorkspaceRepository,
    SqlWorkspaceRepository,
)
from infrastructure.tools.filesystem import FileReadTool, FileRoot
from infrastructure.workspace.context import LocalWorkspaceContext


def context(tmp_path: Path) -> LocalWorkspaceContext:
    return LocalWorkspaceContext(
        path=tmp_path / "ACTIVE_WORKSPACE",
        default_root=tmp_path / "workspace",
        roots_base=tmp_path / "workspaces",
    )


def service(tmp_path: Path) -> WorkspaceService:
    return WorkspaceService(repository=InMemoryWorkspaceRepository(), context=context(tmp_path))


# --- The record ---------------------------------------------------------------


def test_the_id_is_a_slug_of_the_name_and_the_first_one_keeps_its_value() -> None:
    assert slug("Default") == DEFAULT_WORKSPACE_ID
    assert slug("Client A / 2026") == "client-a-2026"


def test_a_name_with_nothing_nameable_in_it_is_refused() -> None:
    with pytest.raises(ValueError):
        slug("///")


async def test_the_default_workspace_exists_without_anybody_creating_it(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlWorkspaceRepository(session_factory)

    first = await repository.ensure_default()
    second = await repository.ensure_default()

    assert first.id == DEFAULT_WORKSPACE_ID
    assert second.created_at == first.created_at  # asserted, never re-created


async def test_a_renamed_default_workspace_keeps_the_name_it_was_given(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = SqlWorkspaceRepository(session_factory)
    await repository.ensure_default()
    await repository.save(Workspace(id=DEFAULT_WORKSPACE_ID, name="Personal", description="mine"))

    assert (await repository.ensure_default()).name == "Personal"


async def test_two_names_that_slug_the_same_way_are_refused(tmp_path: Path) -> None:
    workspaces = service(tmp_path)
    await workspaces.create("Client A")

    with pytest.raises(DuplicateWorkspaceError):
        await workspaces.create("client  a")


async def test_the_first_workspace_cannot_be_removed(tmp_path: Path) -> None:
    with pytest.raises(ProtectedWorkspaceError):
        await service(tmp_path).delete(DEFAULT_WORKSPACE_ID)


# --- The switch ---------------------------------------------------------------


async def test_switching_survives_the_process_that_did_it(tmp_path: Path) -> None:
    shared = InMemoryWorkspaceRepository()
    first = WorkspaceService(repository=shared, context=context(tmp_path))
    await first.create("Work")
    await first.use(WorkspaceId("work"))

    # A second process, reading the same file the first one wrote.
    second = WorkspaceService(repository=shared, context=context(tmp_path))

    assert (await second.active()).id == "work"


async def test_a_switch_file_naming_a_workspace_that_is_gone_lands_on_the_default(
    tmp_path: Path,
) -> None:
    workspaces = service(tmp_path)
    await workspaces.create("Work")
    await workspaces.use(WorkspaceId("work"))
    await workspaces.delete(WorkspaceId("work"))

    assert (await workspaces.active()).id == DEFAULT_WORKSPACE_ID


async def test_a_workspace_can_be_switched_to_by_the_name_a_person_types(
    tmp_path: Path,
) -> None:
    workspaces = service(tmp_path)
    await workspaces.create("Client A")

    assert (await workspaces.use_by_name("Client A")).id == "client-a"
    with pytest.raises(WorkspaceNotFoundError):
        await workspaces.use_by_name("Nobody")


# --- The root that follows it -------------------------------------------------


async def test_a_new_workspace_gets_a_root_of_its_own_outside_the_first_ones(
    tmp_path: Path,
) -> None:
    workspaces = service(tmp_path)
    created = await workspaces.create("Work")

    root = workspaces.root_for(created.id)

    assert root == tmp_path / "workspaces" / "work"
    assert tmp_path / "workspace" not in root.parents


async def test_the_file_tools_read_the_workspace_the_run_is_in(tmp_path: Path) -> None:
    """The root is resolved per call, so switching moves what an employee sees.

    This is the point of §15.3: isolation that stops at the moment somebody
    opens a file is not isolation.
    """
    shared = InMemoryWorkspaceRepository()
    tracker = context(tmp_path)
    workspaces = WorkspaceService(repository=shared, context=tracker)
    await workspaces.create("Work")
    for name, root in (
        ("default", tmp_path / "workspace"),
        ("work", tmp_path / "workspaces" / "work"),
    ):
        root.mkdir(parents=True, exist_ok=True)
        (root / "notes.txt").write_text(name, encoding="utf-8")

    tool = FileReadTool(FileRoot(tracker.current_root))

    assert (await tool.execute({"path": "notes.txt"})).output["content"] == "default"
    await workspaces.use(WorkspaceId("work"))
    assert (await tool.execute({"path": "notes.txt"})).output["content"] == "work"


async def test_a_run_keeps_the_workspace_it_started_in(tmp_path: Path) -> None:
    """A person switching mid-run must not move the root the run resolves against."""
    tracker = context(tmp_path)
    workspaces = WorkspaceService(repository=InMemoryWorkspaceRepository(), context=tracker)
    await workspaces.create("Work")

    with tracker.enter(DEFAULT_WORKSPACE_ID):
        await workspaces.use(WorkspaceId("work"))
        assert tracker.current == DEFAULT_WORKSPACE_ID
        assert tracker.current_root() == tmp_path / "workspace"

    assert tracker.current == "work"


async def test_a_declared_file_root_wins_over_the_derived_one(tmp_path: Path) -> None:
    workspaces = service(tmp_path)
    created = await workspaces.create("Work", file_root=str(tmp_path / "elsewhere"))

    assert workspaces.root_for(created.id) == tmp_path / "elsewhere"
