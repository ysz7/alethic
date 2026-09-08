"""What connecting to an integration produces, in terms nothing external owns.

`Connection` lives here rather than beside the lifecycle that uses it because
both sides need it and neither may import the other: the service in
`application/` receives one, the adapter in `infrastructure/` builds one, and
the layering says they meet in the domain. It is also why `Connector` is a
callable type rather than a class - the service is handed a way to connect,
learns nothing about what protocol is behind it, and an integration of another
kind is a second function of this shape.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from domain.integrations.models import Integration
from domain.tools.protocols import Tool


@dataclass(frozen=True, slots=True)
class Connection:
    """A live integration: what it turned out to offer, and how to end it.

    `close` is held so that whoever opened a server can close it and nothing
    else can. A tool holds its client and the client holds its transport; this
    holds the pair, so "disconnect" is an operation a person can perform rather
    than a process they have to kill.
    """

    integration: Integration
    tools: tuple[Tool, ...] = ()
    close: Callable[[], Any] = lambda: None
    metadata: dict[str, Any] = field(default_factory=dict)


#: Given an integration and the credentials it needs, produce a live connection.
Connector = Callable[[Integration, dict[str, str]], Awaitable[Connection]]
