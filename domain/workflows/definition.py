"""A predefined process, declared rather than coded.

A plan is what Alethic decides an objective takes; a workflow is what somebody
already knows it takes. They run through the same machinery for a reason - the
same employees, the same tools, the same approval gate - and differ only in
where the decomposition came from. That is why a workflow is a declaration and
not a subclass of anything: adding one must not require changing an employee,
and running one must not require a second runtime.

Retry lives on the step (§10.8) rather than on the engine. Whether re-running is
worth it is a property of the work: fetching a page again is free and reasonable,
sending a message again is neither. An engine-wide retry count would have to be
set for the least forgiving step and would then be wrong for every other one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WorkflowTrigger(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    EVENT = "EVENT"
    CONDITIONAL = "CONDITIONAL"


class OnFailure(StrEnum):
    """What the run does when a step is finally out of attempts."""

    #: Nothing after this step runs. The default: a later step usually reads
    #: what an earlier one produced, and running it anyway produces a confident
    #: answer built on a gap.
    STOP = "STOP"
    #: The step is recorded as failed and the run carries on. For a step whose
    #: output is a nice-to-have - a notification, an extra source.
    CONTINUE = "CONTINUE"


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    name: str
    employee: str
    instruction: str
    depends_on: tuple[str, ...] = ()
    #: How many times to run this step before giving up on it. One means no
    #: retry, which is the safe default for anything that touches the world.
    max_attempts: int = 1
    on_failure: OnFailure = OnFailure.STOP


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """A predefined process. Adding one must not require changing any employee."""

    name: str
    description: str = ""
    trigger: WorkflowTrigger = WorkflowTrigger.MANUAL
    steps: tuple[WorkflowStep, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)

    @property
    def employees(self) -> frozenset[str]:
        """Who this workflow needs. What `alethic workflows` checks against."""
        return frozenset(step.employee for step in self.steps)
