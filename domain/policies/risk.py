"""What an action does to the world, and how risky that makes it.

Phase 4 asked each tool to declare a risk level, and that worked while there
were four tools. It does not scale: `RiskLevel.MEDIUM` on a new tool is a
number somebody chose, and the next author choosing differently is invisible in
review. §70 states the rule the numbers were meant to encode - reading is low,
writing is medium, sending, spending, deleting and publishing are high - so the
declaration becomes the *effect* and the level follows from it.

That inverts who is trusted with what. A tool author knows exactly what their
tool does to the world; they should not also have to know what the platform
considers risky about it, because that is a policy decision and policy
decisions belong in one place.

A spec may still declare a level above what its effect implies - a read of
something sensitive is a real case - but never below one, which is enforced in
`ToolSpec.of` rather than left to review.
"""

from __future__ import annotations

from enum import StrEnum

from domain.policies.models import RiskLevel


class Effect(StrEnum):
    """What a call does, in the vocabulary the policy layer reasons about."""

    #: Observes and changes nothing: listing, reading, searching, screenshotting.
    READ = "READ"
    #: Changes something on this machine that the user could put back.
    WRITE = "WRITE"
    #: Runs code the platform did not write.
    EXECUTE = "EXECUTE"
    #: Destroys something. Distinct from WRITE because there is nothing to undo.
    DELETE = "DELETE"
    #: Something leaves this machine addressed to a person: mail, a message.
    SEND = "SEND"
    #: Something becomes visible to people who were not asked: a post, a commit.
    PUBLISH = "PUBLISH"
    #: Money moves.
    SPEND = "SPEND"


#: §70, as a table rather than as a sentence in a prompt. The four HIGH ones are
#: the four §70 names outright; EXECUTE joins them because code the platform did
#: not write can do any of the other three.
EFFECT_RISK: dict[Effect, RiskLevel] = {
    Effect.READ: RiskLevel.LOW,
    Effect.WRITE: RiskLevel.MEDIUM,
    Effect.EXECUTE: RiskLevel.HIGH,
    Effect.DELETE: RiskLevel.HIGH,
    Effect.SEND: RiskLevel.HIGH,
    Effect.PUBLISH: RiskLevel.HIGH,
    Effect.SPEND: RiskLevel.HIGH,
}

#: Effects nothing can undo. A declaration may not call one of these reversible.
IRREVERSIBLE_EFFECTS: frozenset[Effect] = frozenset(
    {Effect.DELETE, Effect.SEND, Effect.PUBLISH, Effect.SPEND}
)

_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


def risk_of(effect: Effect) -> RiskLevel:
    return EFFECT_RISK[effect]


def at_least(level: RiskLevel, threshold: RiskLevel) -> bool:
    return _ORDER[level] >= _ORDER[threshold]


def highest(*levels: RiskLevel) -> RiskLevel:
    return max(levels, key=lambda level: _ORDER[level])
