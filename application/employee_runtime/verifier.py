"""Checks the result against the task. Never assumes success.

The employee that did the work is the wrong witness to whether it worked: a
confident summary is exactly what a failed run also produces. So a separate call
judges the output against the goal, and a task cannot complete without it.

**It is shown what the task did, not only what it said.** Until Phase 16 the
verdict was formed from the summary alone, and the prompt asks it to fail a
result that "claims something it does not show" - so it failed work whose
evidence the platform was holding and did not hand over. The triage step of the
inbox workflow listed a directory, read four files and was rejected twice for
producing "no evidence that the files were read", which stopped the workflow
before a single draft was written. This is the same rule Phase 12 wrote for
accepting a task (`domain.workforce.acceptance`): judge on the record, not on
the report. The two do not merge - that one asks whether the work happened, this
one asks whether it is any good - but they may not disagree about the facts.
"""

from __future__ import annotations

import structlog

from application.prompts import render
from domain.capabilities.models import CapabilityRequirement
from domain.employees.verification import MIN_JUDGEMENT_QUALITY, Verdict
from domain.llm.json_output import extract_object
from domain.llm.models import LLMRequest, Message, RoutingHints, TaskKind
from domain.llm.protocols import LLM
from domain.tasks.plan import TaskPlan
from domain.tasks.task import Task, TaskResult

log = structlog.get_logger(__name__)


class Verifier:
    """Implements `domain.employees.protocols.Verifier`."""

    def __init__(self, llm: LLM) -> None:
        self._llm = llm

    async def verify(
        self, task: Task, result: TaskResult, plan: TaskPlan | None = None
    ) -> Verdict:
        if not result.summary.strip():
            # No model call needed to know that nothing is not an answer.
            return Verdict.rejected("The task produced no output", "any result at all")

        prompt = render(
            "verifier",
            goal=task.goal,
            expected=_expected(plan),
            actions=_actions(result),
            result=result.summary,
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
            # A verifier that cannot be read must not wave the work through.
            log.warning("task.verdict_unreadable", task_id=str(task.id))
            return Verdict.rejected(
                "The verifier did not return a readable verdict", "a second opinion"
            )

        passed = bool(parsed.get("passed", False))
        verdict = Verdict(
            passed=passed,
            reason=str(parsed.get("reason", "")).strip(),
            missing=tuple(
                str(item).strip() for item in parsed.get("missing", ()) if str(item).strip()
            ),
        )
        log.info(
            "task.verified", task_id=str(task.id), passed=verdict.passed, reason=verdict.reason
        )
        return verdict

    @staticmethod
    def routing() -> tuple[TaskKind, CapabilityRequirement, RoutingHints]:
        """Verification is a judgement about text, and it happens once.

        Cheap is fine and cheapest is not: the floor is a requirement, so no
        configured default can route a judgement to a model that answers one by
        echoing the prompt back.
        """
        return (
            TaskKind.VERIFICATION,
            CapabilityRequirement(min_quality=MIN_JUDGEMENT_QUALITY),
            RoutingHints(quality=0.6, cost_sensitivity=0.7),
        )


def _expected(plan: TaskPlan | None) -> str:
    if plan is None or plan.is_empty:
        return "No plan was recorded; judge the result against the task itself."
    lines = [
        f"{step.index + 1}. {step.description}"
        + (f" -> {step.expected_outcome}" if step.expected_outcome else "")
        for step in plan.steps
    ]
    return "\n".join(lines)


def _actions(result: TaskResult) -> str:
    """What the run is recorded as having done, one line per action.

    Read from the result's own observations rather than from a store: the
    verifier runs inside the same stage that produced them, and reaching for a
    repository here would give the check a dependency it does not need and a
    second source of truth it could disagree with.
    """
    observations = result.output.get("observations") or ()
    lines = []
    for entry in observations:
        if not isinstance(entry, dict):
            continue
        details = entry.get("details") or {}
        tool = str(details.get("tool", "")).strip()
        if not tool:
            continue
        outcome = "ok" if entry.get("succeeded", True) else "failed"
        # The name and the outcome, and deliberately not what came back. A first
        # attempt included a truncated trace of the output and the verifier
        # started judging the answer against it: a summary of five meeting notes
        # was failed for naming an owner "not present in the provided text",
        # where the text it had been shown was the first two hundred characters
        # of one file. This section answers whether the action happened. What
        # the action returned is in the result, which is the next section down.
        lines.append(f"- {tool} ({outcome})")
    if not lines:
        return "Nothing was recorded. No tool was called during this task."
    return "\n".join(lines)
