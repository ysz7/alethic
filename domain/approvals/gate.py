"""One rule decides whether an action needs a human: how risky it is.

The temptation is a list of special cases - writes outside the working
directory, deletes, sends, payments. That list is unmaintainable, because every
new tool has to remember to add itself to it, and the one that forgets is the
one that does damage.

So risk is a property of the tool, declared in its `ToolSpec`, and a tool that
can tell the difference between a harmless call and a damaging one refines it
per call through `RiskAssessor`. Creating a new file is LOW; overwriting one
that exists is HIGH. Above the threshold, a human decides.

This module answers one question only - *how risky is this call* - and Phase
10's `domain.policies.rules` answers the other one, *what should happen about
it*. Keeping them apart is what lets an employee's declaration deny an action
that risk alone would have allowed, without either half learning the other's
vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.policies.models import Decision, PolicyDecision, RiskLevel
from domain.policies.risk import at_least, highest
from domain.tools.models import ToolSpec

#: At and above this level, an action waits for a person.
APPROVAL_THRESHOLD = RiskLevel.HIGH

__all__ = [
    "APPROVAL_THRESHOLD",
    "RiskAssessment",
    "assess_call",
    "at_least",
    "describe",
    "resolve_risk",
]


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """What a tool says about one specific call it was asked to make."""

    risk_level: RiskLevel
    reason: str = ""


def resolve_risk(spec: ToolSpec, assessment: RiskAssessment | None = None) -> RiskLevel:
    """How risky this particular call is, spec and per-call judgement combined.

    A tool declared irreversible always waits, whatever it says about the
    individual call - that is what declaring it irreversible means. A reversible
    tool's own assessment of the call wins over its static level, in both
    directions: it knows more about this call than its spec does.
    """
    if spec.reversible:
        return assessment.risk_level if assessment else spec.risk_level
    level = highest(spec.risk_level, APPROVAL_THRESHOLD)
    return highest(level, assessment.risk_level) if assessment is not None else level


def assess_call(spec: ToolSpec, assessment: RiskAssessment | None = None) -> PolicyDecision:
    """Risk alone, with no policy around it: the threshold and nothing else.

    Kept as its own function because it is what the risk *is*, before anything
    an employee declared or a user configured has been applied. The policy
    engine takes this as input; it does not re-derive it.
    """
    level = resolve_risk(spec, assessment)
    reason = assessment.reason if assessment else ""
    if at_least(level, APPROVAL_THRESHOLD):
        return PolicyDecision(
            decision=Decision.REQUIRE_APPROVAL,
            reason=reason or f"{spec.name} is a {level.value.lower()}-risk action",
            risk_level=level,
        )
    return PolicyDecision(decision=Decision.ALLOW, reason=reason, risk_level=level)


def describe(spec: ToolSpec, input_data: dict[str, Any], *, width: int = 120) -> str:
    """The one line a person reads before deciding.

    Arguments are trimmed: a confirmation prompt that scrolls a file's contents
    off the screen is a prompt nobody reads before answering.
    """
    parts = []
    for key, value in sorted(input_data.items()):
        rendered = repr(value)
        if len(rendered) > width:
            rendered = rendered[:width] + "..."
        parts.append(f"{key}={rendered}")
    return f"{spec.name}({', '.join(parts)})"
