"""Turning a stored integration into live tools.

The one seam between the lifecycle in `application/integrations/` and the
protocol in this package. The service is handed a callable; this is what it is
handed on a machine that speaks MCP. Nothing above it imports this module, and
an integration of a different kind is a second function of the same shape rather
than a branch inside the service.

Discovery happens here rather than in the transport because what a server offers
and what the platform makes of it are two different things: the client reports
the claim, `spec_for` decides the effect from the *local* record, and the tool is
built from the second. Keeping that order is ADR 0015 in one function.
"""

from __future__ import annotations

import structlog

from domain.integrations.models import Integration
from domain.integrations.protocols import Connection
from infrastructure.mcp.client import MCPClient
from infrastructure.mcp.transport import DEFAULT_TIMEOUT_SECONDS, ServerCommand, StdioTransport
from infrastructure.tools.mcp import tools_for

log = structlog.get_logger(__name__)


def mcp_connector(*, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
    """A `Connector` for MCP servers spoken to over stdio."""

    async def connect(integration: Integration, environment: dict[str, str]) -> Connection:
        client = MCPClient(
            StdioTransport(
                ServerCommand.from_configuration(integration.configuration),
                timeout_seconds=timeout_seconds,
            )
        )
        await client.connect(environment)
        discovered = await client.list_tools()
        ready = integration.rediscovered(discovered)
        log.info(
            "mcp.integration_ready", integration=ready.name, tools=len(discovered)
        )
        return Connection(
            integration=ready,
            tools=tuple(tools_for(ready, discovered, client)),
            close=client.aclose,
        )

    return connect


def cached_connector(*, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS):
    """A `Connector` that trusts the record instead of starting the server.

    What `restore` uses when a process starts. The tools come from what the
    server said last time, which is on the integration, and the client behind
    them connects on the first call that is actually made - so a runtime with
    ten integrations starts in the time it takes to read ten rows rather than to
    launch ten programs.
    """

    async def connect(integration: Integration, environment: dict[str, str]) -> Connection:
        client = MCPClient(
            StdioTransport(
                ServerCommand.from_configuration(integration.configuration),
                timeout_seconds=timeout_seconds,
            )
        )
        return Connection(
            integration=integration,
            tools=tuple(tools_for(integration, integration.discovered, client)),
            close=client.aclose,
        )

    return connect
