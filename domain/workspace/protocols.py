"""Which workspace the work in front of us belongs to.

Two questions, deliberately answered by one contract because they have to agree.
`active` is what this machine is working in when nobody says otherwise - the
answer the CLI and a new request get. `enter` is what one run is working in,
which is not the same thing: a plan started in one workspace must keep reading
that workspace's files even if the person switches while it runs, and two runs
in different workspaces must not resolve the same relative path to the same
file.

There is no repository row for `active`. Which workspace is active is a fact
about this installation - a file beside the database, the way the stop signal is
- rather than a column, because two processes on one machine may be working in
different workspaces and a row saying which is "the" active one would make the
second one wrong.
"""

from __future__ import annotations

from collections.abc import Iterable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol

from domain.workspace.models import Workspace, WorkspaceId


class WorkspaceContext(Protocol):
    @property
    def active(self) -> WorkspaceId:
        """What this machine works in when a request does not say."""
        ...

    @property
    def current(self) -> WorkspaceId:
        """What the work in front of us belongs to. `active` outside a run."""
        ...

    def use(self, workspace_id: WorkspaceId) -> None:
        """Switch this machine. Survives the process, like the stop signal."""
        ...

    def enter(self, workspace_id: WorkspaceId) -> AbstractContextManager[None]:
        """Carry one run in one workspace, whatever the machine switches to."""
        ...

    def declare(self, workspaces: Iterable[Workspace]) -> None:
        """Tell the context what exists, after a workspace is added or changed."""
        ...

    def root_for(self, workspace_id: WorkspaceId) -> Path:
        """The directory the filesystem tools may see for that workspace."""
        ...

    def current_root(self) -> Path:
        """`root_for(current)`, which is what a file tool asks at call time."""
        ...
