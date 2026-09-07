"""Alethic: the user states a goal, and this decides what happens to it.

`WorkforceManager` in one class. The order is fixed and each step is a component
of its own, because each is a different kind of judgement and they fail in
different ways:

    read it -> (answer it) -> plan it -> delegate and supervise -> check it
             -> (replan once) -> write the answer

Two of those are in brackets, and both are the point of the phase.

**Answering directly.** A request that needs no work gets an answer, not a plan
(§7.5). Decomposition is a means; an objective broken into one task whose whole
content is the question already asked has cost an employee run to restate it.

**Replanning once.** A verdict against the objective's own acceptance criteria
can send the work back through planning, told what was missing - once. A second
rejection usually means the criteria cannot be met by this workforce, and a
third plan spends another budget finding that out again. What is left is
escalated to the user, with what was tried (§7.11).

**Remembering.** What Alethic reads out of a request - how the user wants things
done here - outlives the request, and what a workspace has already learned is
passed down to the tasks it delegates rather than kept for itself. Memory is
optional and reached through a contract, so a manager without one plans exactly
as it did before (§9.4).

What this class does *not* do is as deliberate:

* it never names an employee - candidates come from `EmployeeRegistry`;
* it never runs a task - `TaskExecution` does, and Alethic holds only the contract;
* it never resolves an approval (§7.10). An irreversible action inside a
  delegated task stops at the same gate it would have stopped at if the user had
  asked the employee directly, and the person who answers it is a person. Alethic
  can explain what it is for; it cannot say yes to its own work.
"""

from __future__ import annotations

from dataclasses import replace

import structlog

from application.alethic.intent import IntentReader
from application.alethic.planner import ObjectivePlanner
from application.alethic.supervisor import Recovery, Supervision, Supervisor
from application.alethic.synthesis import Synthesizer, describe
from application.alethic.verification import ObjectiveVerifier
from application.memory.workspace import WorkspaceMemory
from domain.employees.protocols import EmployeeRegistry
from domain.errors import DelegationError
from domain.tasks.progress import NullProgress, ProgressEvent, ProgressKind, ProgressSink
from domain.workforce.assignment import SharedContext
from domain.workforce.intent import Intent
from domain.workforce.protocols import (
    Objective,
    ObjectiveResult,
    ObjectiveStatus,
    Plan,
    PlanStatus,
)
from domain.workforce.repository import ObjectiveRepository, PlanRepository

log = structlog.get_logger(__name__)

#: How many plans one objective is worth. The second is told what the first
#: missed; a third would be told the same thing again.
MAX_PLAN_REVISIONS = 2


class AlethicManager:
    """Implements `domain.workforce.protocols.WorkforceManager`."""

    def __init__(
        self,
        *,
        intent: IntentReader,
        planner: ObjectivePlanner,
        supervisor: Supervisor,
        verifier: ObjectiveVerifier,
        synthesizer: Synthesizer,
        registry: EmployeeRegistry,
        objectives: ObjectiveRepository,
        plans: PlanRepository,
        progress: ProgressSink | None = None,
        max_revisions: int = MAX_PLAN_REVISIONS,
        memory: WorkspaceMemory | None = None,
    ) -> None:
        self._intent = intent
        self._planner = planner
        self._supervisor = supervisor
        self._verifier = verifier
        self._synthesizer = synthesizer
        self._registry = registry
        self._objectives = objectives
        self._plans = plans
        self._progress = progress or NullProgress()
        self._max_revisions = max_revisions
        self._memory = memory

    # --- The whole of it ------------------------------------------------------

    async def receive(self, request: str, workspace_id=None) -> Objective:
        """Turn a sentence into a recorded objective, before anything is done.

        Written down first, like a task is: a process killed one second later
        still leaves a record of what was asked, and the user's own words are
        kept beside whatever Alethic made of them.
        """
        objective = Objective.create(
            request.strip(),
            **({"workspace_id": workspace_id} if workspace_id is not None else {}),
        )
        await self._objectives.save(objective)
        log.info("alethic.objective_received", objective_id=str(objective.id))
        return objective

    async def handle_objective(self, objective: Objective) -> ObjectiveResult:
        """Carry one objective to an answer."""
        workforce = self._registry.list(objective.workspace_id)
        await self._announce(objective, "Working out what you are asking for.")

        # Recalled before the request is read, not after it is planned. A
        # request written against the last one - "do the same for the returns
        # folder" - cannot be understood without what the last one was, and
        # every stage below reads better for having it.
        remembered = await self._remembered(objective)

        intent = await self._intent.read(objective.text, workforce, remembered=remembered)
        objective = self._understood(objective, intent)
        await self._objectives.save(objective)
        if self._memory is not None and intent.preferences:
            # A preference stated in passing - "always in Markdown", "never
            # touch the originals" - is stated once and expected to hold. It is
            # kept here, where it was read, rather than at the end, where a
            # failed objective would take it down with it.
            #
            # `intent.constraints` is deliberately not kept: those describe this
            # request, and remembering them as standing preferences is what sent
            # the second validation run back to the first one's folder.
            await self._memory.remember_preferences(
                intent.preferences,
                source=objective.text,
                workspace_id=objective.workspace_id,
            )

        if intent.is_answerable_directly:
            return await self._answer_directly(objective, intent)

        try:
            return await self._work(objective, intent, remembered)
        except DelegationError as error:
            # Nothing to delegate to is the user's to fix, not something to
            # replan around: every plan would end in the same place.
            return await self._finish(
                objective,
                ObjectiveStatus.ESCALATED,
                summary=str(error),
                missing=("someone declared who can do this work",),
            )

    # --- The two routes -------------------------------------------------------

    async def _answer_directly(
        self, objective: Objective, intent: Intent
    ) -> ObjectiveResult:
        """No plan, no employee, no tools (§7.5)."""
        log.info("alethic.answered_directly", objective_id=str(objective.id))
        if self._memory is not None:
            # Nothing else records this: no task ran, so without it the only
            # trace that the question was asked is the objective row.
            await self._memory.remember_answer(
                objective.text, intent.answer, workspace_id=objective.workspace_id
            )
        return await self._finish(
            objective,
            ObjectiveStatus.DONE,
            summary=intent.answer,
            output={"delegated": False, "restatement": intent.restatement},
        )

    async def _work(
        self, objective: Objective, intent: Intent, remembered: tuple[str, ...] = ()
    ) -> ObjectiveResult:
        workforce = self._registry.list(objective.workspace_id)
        objective = objective.to(ObjectiveStatus.PLANNING)
        await self._objectives.save(objective)

        feedback: tuple[str, ...] = ()
        supervision: Supervision | None = None
        plan: Plan | None = None
        cost = 0.0

        for revision in range(1, self._max_revisions + 1):
            plan = await self._planner.plan(
                objective,
                workforce,
                restatement=intent.restatement,
                revision=revision,
                feedback=feedback,
                remembered=remembered,
            )
            await self._plans.save(plan)
            await self._announce(
                objective,
                plan.rationale or f"{len(plan.tasks)} task(s) planned.",
                kind=ProgressKind.PLAN,
                payload={
                    "plan_id": str(plan.id),
                    "revision": revision,
                    "tasks": [
                        {"id": str(task.id), "goal": task.goal} for task in plan.tasks
                    ],
                },
            )

            objective = objective.to(ObjectiveStatus.RUNNING)
            await self._objectives.save(objective)
            plan = plan.to(PlanStatus.RUNNING)
            await self._plans.save(plan)

            supervision = await self._supervisor.run(
                plan,
                context=SharedContext(
                    facts=remembered, constraints=tuple(intent.acceptance_criteria)
                ),
                objective_id=objective.id,
            )
            cost += supervision.cost_usd

            verdict = await self._verifier.verify(
                objective, describe(supervision.outcomes)
            )
            await self._plans.save(
                plan.to(PlanStatus.DONE if verdict.passed else PlanStatus.FAILED)
            )

            if verdict.passed:
                return await self._deliver(objective, supervision, cost=cost)

            feedback = verdict.missing or (verdict.reason,)
            log.info(
                "alethic.objective_rejected",
                objective_id=str(objective.id),
                revision=revision,
                missing=list(feedback),
            )
            if revision < self._max_revisions and supervision.recovery is not Recovery.GIVE_UP:
                await self._plans.save(plan.superseded())
                await self._announce(
                    objective,
                    "That did not meet what you asked for. Planning a second attempt.",
                    payload={"missing": list(feedback)},
                )
                continue
            break

        # Out of revisions. Hand back what there is, and say what is missing.
        return await self._escalate(objective, supervision, feedback, cost=cost)

    # --- Endings --------------------------------------------------------------

    async def _deliver(
        self, objective: Objective, supervision: Supervision, *, cost: float
    ) -> ObjectiveResult:
        summary = await self._synthesizer.synthesize(objective, supervision.outcomes)
        return await self._finish(
            objective,
            ObjectiveStatus.DONE,
            summary=summary,
            output=_evidence(supervision),
            cost_usd=cost,
        )

    async def _escalate(
        self,
        objective: Objective,
        supervision: Supervision | None,
        missing: tuple[str, ...],
        *,
        cost: float,
    ) -> ObjectiveResult:
        """Give the user what there is, plus what was tried and what is absent.

        Escalation is not failure with a nicer name: the work that succeeded is
        still handed over, and the history of attempts is what makes the request
        actionable rather than a shrug (§7.11).
        """
        outcomes = supervision.outcomes if supervision else ()
        summary = (
            await self._synthesizer.synthesize(objective, outcomes, missing=missing)
            if outcomes
            else "Nothing could be produced for this objective."
        )
        log.info(
            "alethic.escalated",
            objective_id=str(objective.id),
            attempts=len(outcomes),
            missing=list(missing),
        )
        return await self._finish(
            objective,
            ObjectiveStatus.ESCALATED,
            summary=summary,
            output=_evidence(supervision) if supervision else {},
            missing=missing,
            cost_usd=cost,
        )

    async def _finish(
        self,
        objective: Objective,
        status: ObjectiveStatus,
        *,
        summary: str,
        output: dict[str, object] | None = None,
        missing: tuple[str, ...] = (),
        cost_usd: float = 0.0,
    ) -> ObjectiveResult:
        result = ObjectiveResult(
            objective_id=objective.id,
            summary=summary,
            status=status,
            output=dict(output or {}),
            missing=missing,
            cost_usd=cost_usd,
        )
        await self._objectives.save(objective.to(status, result))
        await self._announce(
            objective,
            summary,
            kind=ProgressKind.RESULT,
            payload={"status": status.value, "missing": list(missing), "cost_usd": cost_usd},
        )
        log.info(
            "alethic.objective_finished",
            objective_id=str(objective.id),
            status=status.value,
            cost_usd=round(cost_usd, 6),
        )
        return result

    # --- Internals ------------------------------------------------------------

    async def _remembered(self, objective: Objective) -> tuple[str, ...]:
        """What this workspace knows that bears on this request.

        Read once per objective and used everywhere: by the reading of the
        request, by the decomposition, and by every task in the plan. Recalling
        it per stage would cost the same query three times and could answer it
        three different ways.
        """
        if self._memory is None:
            return ()
        return await self._memory.context_for(
            objective.text, workspace_id=objective.workspace_id
        )

    @staticmethod
    def _understood(objective: Objective, intent: Intent) -> Objective:
        """What Alethic read, recorded next to what was said - never instead of it."""
        return replace(
            objective,
            constraints={**objective.constraints, **intent.constraints},
            acceptance_criteria=intent.acceptance_criteria,
        )

    async def _announce(
        self,
        objective: Objective,
        message: str,
        *,
        kind: ProgressKind = ProgressKind.STAGE,
        payload: dict[str, object] | None = None,
    ) -> None:
        try:
            await self._progress.emit(
                ProgressEvent(
                    task_id=objective.id,
                    objective_id=objective.id,
                    kind=kind,
                    message=message,
                    payload=dict(payload or {}),
                    workspace_id=objective.workspace_id,
                )
            )
        except Exception as error:  # a watcher must not be able to fail a run
            log.warning("progress.emit_failed", error=str(error))


def _evidence(supervision: Supervision) -> dict[str, object]:
    """What the answer rests on, so it can be checked rather than believed."""
    progress = supervision.progress
    return {
        "delegated": True,
        "plan_id": str(supervision.plan.id),
        "revision": supervision.plan.revision,
        "tasks": [
            {
                "id": str(outcome.task.id),
                "goal": outcome.task.goal,
                "employee": outcome.employee,
                "status": outcome.task.status.value,
                "cost_usd": round(outcome.task.cost_usd, 6),
            }
            for outcome in supervision.outcomes
        ],
        "completed": progress.completed,
        "failed": progress.failed,
    }
