from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.capabilities.models import Capability
from domain.computer.interfaces import InterfaceLevel
from domain.policies.models import RiskLevel
from domain.policies.risk import Effect, highest, risk_of
from domain.tools.schema import Param, ParameterSet


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """What a model is told about a tool, plus what the platform needs to gate it."""

    name: str
    description: str
    json_schema: dict[str, Any] = field(default_factory=dict)
    #: What this call does to the world. The risk level follows from it
    #: (`domain.policies.risk`), so a tool author declares what their tool does
    #: and not what the platform should think about it.
    effect: Effect = Effect.READ
    risk_level: RiskLevel = RiskLevel.LOW
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    reversible: bool = True
    #: How this tool reaches the world. The default is API because a tool that
    #: does not say otherwise is a direct call - the filesystem, a search
    #: endpoint - and only the tools that really do drive a screen should have
    #: to declare that they do. See `domain.computer.interfaces`.
    interface_level: InterfaceLevel = InterfaceLevel.API
    #: The declared parameters, kept alongside the rendered schema so the same
    #: declaration both describes the tool and validates the call.
    parameters: ParameterSet = field(default_factory=ParameterSet)

    @classmethod
    def of(
        cls,
        name: str,
        description: str,
        *parameters: Param,
        effect: Effect = Effect.READ,
        risk_level: RiskLevel = RiskLevel.LOW,
        capabilities: frozenset[Capability] = frozenset(),
        reversible: bool = True,
        interface_level: InterfaceLevel = InterfaceLevel.API,
    ) -> ToolSpec:
        """Declare a tool once; the JSON Schema is derived, never hand-written.

        `risk_level` may raise what the effect implies and never lower it: a
        read of something sensitive is a real case, a "harmless" delete is not.
        """
        parameter_set = ParameterSet(parameters)
        return cls(
            name=name,
            description=description,
            json_schema=parameter_set.to_json_schema(),
            effect=effect,
            risk_level=highest(risk_level, risk_of(effect)),
            capabilities=capabilities,
            reversible=reversible,
            interface_level=interface_level,
            parameters=parameter_set,
        )


@dataclass(frozen=True, slots=True)
class ToolCall:
    name: str
    input_data: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    success: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latency_ms: int = 0

    @classmethod
    def ok(cls, **output: Any) -> ToolResult:
        return cls(success=True, output=output)

    @classmethod
    def failure(cls, error: str) -> ToolResult:
        return cls(success=False, error=error)
