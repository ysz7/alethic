"""The workspace: what separates one context of work from another.

Every user-owned entity has carried a `workspace_id` since migration 001, and
until Phase 15 it always held 'default': the column was laid through the
manager, the planner, the supervisor and memory before there was anything to
put in it, precisely so that the day there was, nothing above had to be
rewritten. Migration 014 is that day - the column gets a table, a name and a
description, and stays exactly what it was.

There is still no organization, user or membership table. A workspace separates
one person's contexts from each other, not one person from another; multi-tenancy
is a further migration and not this one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final, NewType

WorkspaceId = NewType("WorkspaceId", str)

DEFAULT_WORKSPACE_ID: Final[WorkspaceId] = WorkspaceId("default")


@dataclass(frozen=True, slots=True)
class WorkspaceScope:
    """The workspace a piece of work belongs to."""

    workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID

    @classmethod
    def local(cls) -> WorkspaceScope:
        """The single workspace of a local-first installation."""
        return cls(DEFAULT_WORKSPACE_ID)


def slug(name: str) -> WorkspaceId:
    """The id a workspace gets from its name.

    Readable rather than a uuid: `workspace_id` is on every row of every table
    and in every log line, and 'default' - the value thirteen migrations have
    already written - is what this function returns for "Default". A uuid here
    would have made the first workspace's id a value nothing could reproduce.
    """
    kept = [character.lower() if character.isalnum() else "-" for character in name.strip()]
    collapsed = "-".join(part for part in "".join(kept).split("-") if part)
    if not collapsed:
        raise ValueError("A workspace name must contain something nameable")
    return WorkspaceId(collapsed[:64])


@dataclass(frozen=True, slots=True)
class Workspace:
    """One separation of contexts: work, personal, a client, a project.

    The column has been on every user-owned row since migration 001 and always
    held 'default'; this is the table it names (§71c). Nothing below had to
    change to gain it, which is what paying for the column early bought.

    `file_root` is a column rather than a key in `settings` because it is an
    access boundary: switching workspace moves what the filesystem tools can
    see, and isolation that stops at the moment an employee opens a file is not
    isolation. Unset means the machine's configured root, which is what a
    single-workspace installation has always used.
    """

    id: WorkspaceId
    name: str
    description: str = ""
    file_root: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        name: str,
        *,
        description: str = "",
        file_root: str | None = None,
        **extra: Any,
    ) -> Workspace:
        return cls(
            id=slug(name),
            name=name.strip(),
            description=description,
            file_root=file_root,
            **extra,
        )

    @property
    def is_default(self) -> bool:
        return self.id == DEFAULT_WORKSPACE_ID


#: The first workspace, and the one every existing row already belongs to. It
#: is created by migration 014 rather than lazily by whoever asks first, so a
#: fresh install and an upgraded one hold the same row.
DEFAULT_WORKSPACE_NAME: Final[str] = "Default"
