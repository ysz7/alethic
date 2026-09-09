"""Why a real request did not work, in the terms that change what to build next.

`application/orchestrator.py` already classifies failures, and this is not a
second copy of it. That one answers *should we try again* and has four answers
because four is all a retry decision needs. This one answers *what is missing
from the platform*, and its categories are the ones the roadmap is written in
(§11.3): a run that failed because nobody is declared for the work and a run
that failed because the model lost the thread are both PERMANENT to the
orchestrator and are entirely different pieces of work to fix.

The classification reads types and counters, never message text - the same rule
that governs the retry decision, for the stronger reason that these numbers are
compared across weeks. A taxonomy that depends on the wording of an error moves
whenever somebody improves the wording.
"""

from __future__ import annotations

from enum import StrEnum

from domain.errors import (
    ApprovalDeniedError,
    ApprovalRequiredError,
    ComputerUseError,
    ConfigurationError,
    DelegationError,
    LimitExceededError,
    PermissionDeniedError,
    PlanningError,
    ProviderError,
    StopRequestedError,
    ToolInputError,
    ToolNotFoundError,
)
from domain.validation.evidence import CheckResult, Evidence


class FailureKind(StrEnum):
    """What was at fault. One of these per failed run, and never two."""

    NONE = "NONE"
    #: No usable plan, or a plan that decomposed the request into the wrong
    #: work. The most expensive kind to find and the cheapest to fix.
    PLANNING = "PLANNING"
    #: The screen was misread, or an action on it did not land.
    COMPUTER_USE = "COMPUTER_USE"
    #: A tool was called and did not do its job - wrong arguments it kept
    #: repeating, an adapter that raised, a page that would not load.
    TOOL = "TOOL"
    #: What should have been recalled was not, or what was recalled misled.
    MEMORY = "MEMORY"
    #: The provider failed, or the model did - lost the thread, ignored the
    #: instruction, wrote a closing message instead of doing the work.
    MODEL = "MODEL"
    #: Nothing declared here can do this. Not a bug: a piece of roadmap.
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    #: The work stopped at the gate and no person was there. Correct behaviour
    #: and still a failed run, which is exactly why it has its own name.
    NEEDED_APPROVAL = "NEEDED_APPROVAL"
    #: Steps, money or wall time ran out. Distinct from PLANNING because the
    #: answer is usually a number in a declaration rather than a better plan.
    BUDGET = "BUDGET"
    #: The work ran, finished, and produced something other than what was
    #: asked for. Nothing broke; the result is simply not the result.
    EXPECTATION = "EXPECTATION"
    #: The machine is set up wrong. Counted apart so it never inflates the
    #: platform's own failure rate.
    ENVIRONMENT = "ENVIRONMENT"
    #: None of the above, which is a finding in itself and should be rare.
    UNKNOWN = "UNKNOWN"


#: Exception types whose meaning here is fixed, most specific first. Order
#: matters: `StopRequestedError` and `ComputerUseError` are both execution
#: errors, and `LimitExceededError` is one too.
_BY_TYPE: tuple[tuple[type[BaseException], FailureKind], ...] = (
    (PlanningError, FailureKind.PLANNING),
    (StopRequestedError, FailureKind.COMPUTER_USE),
    (ComputerUseError, FailureKind.COMPUTER_USE),
    (DelegationError, FailureKind.MISSING_CAPABILITY),
    (ApprovalRequiredError, FailureKind.NEEDED_APPROVAL),
    (ApprovalDeniedError, FailureKind.NEEDED_APPROVAL),
    (PermissionDeniedError, FailureKind.NEEDED_APPROVAL),
    (LimitExceededError, FailureKind.BUDGET),
    (ToolNotFoundError, FailureKind.MISSING_CAPABILITY),
    (ToolInputError, FailureKind.TOOL),
    (ProviderError, FailureKind.MODEL),
    (ConfigurationError, FailureKind.ENVIRONMENT),
)


def from_error(error: BaseException) -> FailureKind:
    """What an exception that ended a run says about the platform."""
    for error_type, kind in _BY_TYPE:
        if isinstance(error, error_type):
            return kind
    return FailureKind.UNKNOWN


def classify(
    evidence: Evidence,
    checks: tuple[CheckResult, ...] = (),
    *,
    error: BaseException | None = None,
    memory_expected: bool = False,
    expected_denials: frozenset[str] = frozenset(),
) -> FailureKind:
    """One verdict about why this run is not a pass, or NONE if it is.

    The order below is the order of certainty, not of severity. An exception
    says what happened; a refusal in the audit says it almost as clearly; a
    count of failed tool calls is weaker evidence than either; and "everything
    ran and the answer is wrong" is what is left when nothing else spoke.
    """
    if error is not None:
        return from_error(error)

    # The declared expectations are the whole of the standard, and that
    # includes `must_succeed: false`. Requiring `evidence.succeeded` on top of
    # them made a scenario whose point is that the platform refuses - the
    # workflow that stops where the sending would have been - unable to pass at
    # all: the run correctly did not succeed, every check about that passed, and
    # the verdict blamed the refusal it was written to observe.
    failed = tuple(result for result in checks if not result.passed)
    if not failed:
        return FailureKind.NONE

    # A refusal is the loudest thing in an audit log, and it explains the run
    # whether or not the work also went wrong afterwards: nothing downstream of
    # a denied action was working from what it expected.
    # Only an actual refusal, never merely having been asked. A question that
    # was answered yes changed nothing about the run, and the first full pass
    # blamed approvals for a run whose work had gone through and whose verifier
    # then rejected a correct result. Every refusal reaches the audit as DENIED,
    # so nothing is lost by dropping the weaker signal.
    # A denial the scenario declared is evidence the brake held, not evidence
    # of what went wrong afterwards: `tools_denied` in an expectation is the
    # author saying beforehand that this call must not go through. Blaming it
    # sent every such run to the report under NEEDED_APPROVAL, which is the one
    # category the roadmap reads as "a person had to be there".
    unexpected = tuple(name for name in evidence.tools_denied if name not in expected_denials)
    if unexpected:
        return FailureKind.NEEDED_APPROVAL

    if memory_expected and evidence.metrics.recalled == 0:
        return FailureKind.MEMORY

    if evidence.tools_failed:
        return FailureKind.TOOL

    # Nothing was attempted at all, and the standard was not met. Whether the
    # platform thought it had succeeded makes no difference to what is wrong:
    # deciding a request needs no work is a planning decision, and this one
    # decided wrong. The first full validation pass found exactly this - a
    # request to read a folder of notes and leave a summary file was answered
    # directly, in one sentence, with no task and no tool - and it was recorded
    # as EXPECTATION, which pointed at the answer rather than at the decision
    # that produced it.
    if evidence.metrics.tool_calls == 0 and evidence.metrics.steps == 0:
        return FailureKind.PLANNING

    if not evidence.succeeded:
        return FailureKind.MODEL

    return FailureKind.EXPECTATION
