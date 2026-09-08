"""The three things the platform asks of an MCP server.

Initialize, list what it offers, call one of them. That is the whole of the
protocol as far as Alethic is concerned, and keeping it that small is what keeps
`application/` from ever needing to know the word MCP: above this, a discovered
tool is a `Tool` and nothing else.

The content of a reply is treated as text and never as structure to act on. A
server that returns something unexpected produces a readable failure rather than
an exception from three frames deep - it is an untrusted process, and the first
thing it can do to this platform is answer badly.
"""

from __future__ import annotations

from typing import Any

import structlog

from domain.errors import IntegrationProtocolError
from domain.integrations.models import DiscoveredTool
from infrastructure.mcp.transport import StdioTransport

log = structlog.get_logger(__name__)

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "alethic", "version": "1"}


class MCPClient:
    """One connected server, in the terms the platform uses."""

    def __init__(self, transport: StdioTransport) -> None:
        self._transport = transport
        self._connected = False

    async def connect(self, env: dict[str, str] | None = None) -> None:
        """Start the server and complete the handshake. Idempotent."""
        if self._connected:
            return
        await self._transport.start(env)
        await self._transport.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        await self._transport.notify("notifications/initialized")
        self._connected = True

    async def list_tools(self) -> tuple[DiscoveredTool, ...]:
        """What the server says it offers.

        Every field is treated as a claim: a tool with no usable name is
        dropped rather than registered under an empty string, and the schema is
        kept only if it is an object. What is *done* with these - what effect
        they are given, who may call them - is decided locally (ADR 0015).
        """
        result = await self._transport.request("tools/list")
        raw = (result or {}).get("tools") if isinstance(result, dict) else None
        if not isinstance(raw, list):
            raise IntegrationProtocolError(
                "the server answered tools/list without a list of tools"
            )
        discovered = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            schema = entry.get("inputSchema")
            discovered.append(
                DiscoveredTool(
                    name=name,
                    description=str(entry.get("description", "")),
                    json_schema=schema if isinstance(schema, dict) else {},
                )
            )
        log.info("mcp.tools_discovered", count=len(discovered))
        return tuple(discovered)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call one tool and return what it produced, as text.

        Text rather than the raw structure on purpose: this content is going
        into a transcript and then to a model, and it is the untrusted half of
        the system. Flattening it here means there is one place that decides
        what an external service is allowed to put in front of a model, and it
        is above the transport rather than scattered through the caller.
        """
        result = await self._transport.request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        if not isinstance(result, dict):
            raise IntegrationProtocolError(
                f"{name} answered with {type(result).__name__}, not an object"
            )
        if result.get("isError"):
            raise IntegrationProtocolError(f"{name} reported an error: {_text(result)}")
        return _text(result)

    async def aclose(self) -> None:
        self._connected = False
        await self._transport.aclose()


def _text(result: dict[str, Any]) -> str:
    """The readable part of a tool result, whatever else came with it."""
    content = result.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in parts if part)
