"""The policy contract: what is asked of the engine, and what it answers.

§67's rule is that policies never live inside prompts. What that buys is
testability - "never send email" written in a system prompt is a suggestion a
model weighs against everything else it was told, while `EMAIL_SEND =
REQUIRE_APPROVAL` is a value a test can assert on and a model cannot argue with.

So the request carries everything a decision can depend on and the engine reads
nothing else: no clock, no database, no settings. `domain.policies.rules` is the
implementation, and its purity is the point rather than an accident - a decision
that cannot be reproduced from its inputs cannot be audited.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from domain.policies.models import Actor, PolicyDecision, RiskLevel
from domain.policies.risk import Effect


@dataclass(frozen=True, slots=True)
class PolicyRequest:
    """One action, described in full, with nothing left to look up.

    `policies` is what the actor's own declaration opted into. It is carried
    here rather than read off the `Actor` because the protocol is what every
    caller - the user, Alethic, an employee - already satisfies, and widening it
    would make a policy layer a prerequisite for having an identity.
    """

    actor: Actor
    action: str
    tool: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    effect: Effect = Effect.READ
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    policies: frozenset[str] = field(default_factory=frozenset)
    #: Why the risk came out the way it did, from the tool's own assessment of
    #: this call. Passed through to the person who has to decide.
    risk_reason: str = ""


class PolicyEngine(Protocol):
    def evaluate(self, request: PolicyRequest) -> PolicyDecision: ...
