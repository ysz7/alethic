"""What the platform tells a model about a tool it discovered.

In the domain rather than beside the MCP adapter because none of it is about
MCP: it reads the local effect map, applies the same effect-to-risk table every
written tool goes through, and produces a `ToolSpec`. Keeping it here is also
what lets the interface layer show a person what an integration's tools would
cost - which action asks, which does not - without importing an adapter, and
without restating the rule in a second place where it could disagree.

The server's own sentence becomes the description and decides nothing else. It
is shown to a model and read by a person; the effect comes from the record
(ADR 0015).
"""

from __future__ import annotations

from domain.integrations.models import DiscoveredTool, Integration
from domain.policies.risk import IRREVERSIBLE_EFFECTS
from domain.tools.models import ToolSpec


def spec_for(integration: Integration, discovered: DiscoveredTool) -> ToolSpec:
    """One discovered tool, as the platform will treat it."""
    effect = integration.effect_for(discovered.name)
    return ToolSpec.from_json_schema(
        integration.qualified(discovered.name),
        discovered.description or f"{discovered.name}, offered by {integration.name}.",
        discovered.json_schema,
        effect=effect,
        capabilities=integration.granted_capabilities,
        # Declared from what the effect is, not from what the server implies:
        # a send and a delete cannot be undone whoever offers them.
        reversible=effect not in IRREVERSIBLE_EFFECTS,
    )
