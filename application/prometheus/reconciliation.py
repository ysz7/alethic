"""When two employees disagree (§87).

Everything else in this package judges work against a standard: the verifier
asks whether the objective's criteria are met, acceptance asks whether anything
actually happened. This asks a question neither of them can - whether the
results are *consistent with each other* - and it exists because a plan with
several people on it can produce two answers that are each defensible and
cannot both be true. Synthesis would then blend them into one confident
paragraph, which is the worst available outcome: wrong, and unfalsifiable.

Three rules hold it up, and each rejects an easier alternative.

**One result cannot contradict itself.** Nothing runs unless at least two tasks
succeeded, so the ordinary single-task plan - which is most of them - pays
nothing for this. A structural gate, checked before the model is reached.

**An unresolved conflict is escalated, never synthesised.** Prometheus resolves what
the reports themselves settle - one showed its working, one was about something
else, one is out of date - and hands the rest to the user with both sides named.
That is §87 exactly: resolve, or escalate. Averaging is not a third option, and
"prefer the more confident report" is how a manager launders a guess into an
answer.

**An unreadable answer means consistent.** The opposite of everywhere else in
this package, and deliberately so: a verifier that cannot be read must not wave
work through, because its job is to doubt. This one's job is to notice
something unusual, and a parse failure is not evidence of a contradiction. A
check that escalates whenever its model stutters teaches the user to ignore it.

That last rule used to sit awkwardly with the prompt, which asked for a
`consistent` boolean and had to show it as `true` - the one value in any form
here that a model was invited to copy, and the reason this prompt sat in
`tests/unit/test_prompt_forms.py`'s queue. Phase 18 dropped the field instead of
emptying it: the list of contradictions was always the specific claim, and
consistency is now read off it. The safe answer and the empty form are the same
answer, which is what the rule wanted all along.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from application.prompts import render
from domain.capabilities.models import CapabilityRequirement
from domain.employees.verification import MIN_JUDGEMENT_QUALITY
from domain.llm.json_output import extract_object
from domain.llm.models import LLMRequest, Message, RoutingHints, TaskKind
from domain.llm.protocols import LLM
from domain.workforce.protocols import Objective

log = structlog.get_logger(__name__)

#: Below this, there is nothing to reconcile: a single report cannot disagree
#: with itself, and asking a model whether it does costs a call to be told so.
MIN_RESULTS = 2


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """Whether the reports agree, and what the manager did about it."""

    consistent: bool = True
    conflicts: tuple[str, ...] = ()
    #: Which side stands and why, when the reports themselves settled it.
    resolution: str = ""

    @property
    def resolved(self) -> bool:
        return bool(self.resolution.strip())

    @property
    def escalate(self) -> bool:
        """A contradiction nothing in the evidence settles. The user's call."""
        return not self.consistent and not self.resolved


class Reconciler:
    """Reads several reports and asks whether they can all be true."""

    def __init__(self, llm: LLM, *, minimum: int = MIN_RESULTS) -> None:
        self._llm = llm
        self._minimum = minimum

    async def reconcile(self, objective: Objective, results: tuple[str, ...]) -> Reconciliation:
        reports = tuple(text.strip() for text in results if text.strip())
        if len(reports) < self._minimum:
            return Reconciliation()

        prompt = render(
            "prometheus_reconciliation",
            objective=objective.text,
            results="\n\n".join(f"## Report {i + 1}\n\n{text}" for i, text in enumerate(reports)),
        )
        response = await self._llm.generate(
            LLMRequest(
                messages=(Message.user(prompt),),
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        )

        parsed = extract_object(response.content)
        if parsed is None:
            log.warning("prometheus.reconciliation_unreadable", objective_id=str(objective.id))
            return Reconciliation()

        raw = parsed.get("conflicts") or ()
        conflicts = (
            tuple(text for item in raw if (text := str(item).strip()))
            if isinstance(raw, list | tuple)
            else ()
        )
        # There is no `consistent` field to disagree with: the list of
        # contradictions was always the specific claim, and a boolean beside it
        # could only ever be the vaguer half of a self-contradiction. No
        # conflicts named is agreement, and so is an answer that named none
        # because it could not be read.
        consistent = not conflicts
        resolution = (
            str(parsed.get("resolution", "")).strip()
            if bool(parsed.get("resolvable", False))
            else ""
        )

        reconciliation = Reconciliation(
            consistent=consistent, conflicts=conflicts, resolution=resolution
        )
        if not consistent:
            log.info(
                "prometheus.results_conflict",
                objective_id=str(objective.id),
                conflicts=list(conflicts),
                resolved=reconciliation.resolved,
            )
        return reconciliation

    @staticmethod
    def routing() -> tuple[TaskKind, CapabilityRequirement, RoutingHints]:
        """Deciding which of two people is right is a judgement, and it takes one."""
        return (
            TaskKind.VERIFICATION,
            CapabilityRequirement(min_quality=MIN_JUDGEMENT_QUALITY),
            RoutingHints(quality=0.8, cost_sensitivity=0.3),
        )
