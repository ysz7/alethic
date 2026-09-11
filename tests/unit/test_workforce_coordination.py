"""Phase 12: several people on one objective.

Three claims, and each is the plan's own words turned into a test. Independent
tasks run at once (12.1). What one employee learns reaches another only through
the coordinator, and only where the plan said so (12.2, 12.3, 12.5). And Prometheus
accepts a result on the evidence rather than on the report (12.7).
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

from application.prometheus.delegation import CapabilityDelegator
from application.prometheus.supervisor import Supervisor
from application.workforce.coordinator import WorkforceCoordinator
from domain.tasks.task import Task, TaskCreatedBy, TaskResult, TaskStatus
from domain.workforce.acceptance import accept
from domain.workforce.assignment import SharedContext, TaskAssignment
from domain.workforce.protocols import Plan
from tests.fakes.employees import definition
from tests.fakes.llm import FakeLLM
from tests.fakes.workforce import FakeRegistry, RecordingExecution

WORKER = definition("worker", tools=frozenset({"fs.read"}))


def task(goal: str, plan_id) -> Task:
    return replace(
        Task.create(goal, created_by=TaskCreatedBy.PROMETHEUS), plan_id=plan_id
    )


def plan_of(*goals: str, edges: tuple[tuple[int, int], ...] = ()) -> Plan:
    """A plan whose edges are given as index pairs: (task, depends_on)."""
    plan_id = uuid4()
    tasks = tuple(task(goal, plan_id) for goal in goals)
    return Plan(
        id=plan_id,
        objective_id=uuid4(),
        tasks=tasks,
        dependencies=tuple((tasks[a].id, tasks[b].id) for a, b in edges),
    )


def supervisor(execution: RecordingExecution, **extra) -> Supervisor:
    return Supervisor(
        execution=execution,
        delegator=CapabilityDelegator(FakeLLM([]), FakeRegistry(WORKER)),
        max_attempts=1,
        **extra,
    )


# --- 12.1 Independent tasks run at once ---------------------------------------


async def test_independent_tasks_run_at_the_same_time() -> None:
    """`Plan.ready` always returned them together; now they are started together."""
    running = 0
    peak = 0

    async def slow(task: Task, assignment: TaskAssignment) -> Task:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0)
        running -= 1
        return replace(task, status=TaskStatus.COMPLETED, result=TaskResult(summary="ok"))

    execution = RecordingExecution()
    execution.start = slow  # type: ignore[method-assign]

    plan = plan_of("a", "b", "c")
    await supervisor(execution).run(plan)

    assert peak == 3


async def test_a_chain_still_runs_in_order() -> None:
    order: list[str] = []

    async def note(task: Task, assignment: TaskAssignment) -> Task:
        order.append(task.goal)
        return replace(task, status=TaskStatus.COMPLETED, result=TaskResult(summary="ok"))

    execution = RecordingExecution()
    execution.start = note  # type: ignore[method-assign]

    await supervisor(execution).run(plan_of("first", "second", edges=((1, 0),)))

    assert order == ["first", "second"]


async def test_the_limit_is_a_wave_not_a_failure() -> None:
    """A plan wider than the limit runs in two goes rather than refusing."""
    seen: list[int] = []
    running = 0

    async def slow(task: Task, assignment: TaskAssignment) -> Task:
        nonlocal running
        running += 1
        seen.append(running)
        await asyncio.sleep(0)
        running -= 1
        return replace(task, status=TaskStatus.COMPLETED, result=TaskResult(summary="ok"))

    execution = RecordingExecution()
    execution.start = slow  # type: ignore[method-assign]

    supervision = await supervisor(execution, max_parallel=2).run(plan_of("a", "b", "c", "d"))

    assert max(seen) == 2
    assert len(supervision.outcomes) == 4
    assert supervision.all_succeeded


async def test_a_failure_ends_the_plan_but_not_the_wave() -> None:
    """Its neighbours never depended on it, and their work stands."""

    async def one_fails(task: Task, assignment: TaskAssignment) -> Task:
        if task.goal == "b":
            return replace(task, status=TaskStatus.FAILED)
        return replace(task, status=TaskStatus.COMPLETED, result=TaskResult(summary="ok"))

    execution = RecordingExecution()
    execution.start = one_fails  # type: ignore[method-assign]

    supervision = await supervisor(execution).run(
        plan_of("a", "b", "c", "later", edges=((3, 0),))
    )

    finished = {outcome.task.goal for outcome in supervision.outcomes}
    assert finished == {"a", "b", "c"}, "the whole wave ran; the next one did not"
    assert supervision.recovery is not None


# --- 12.2, 12.3, 12.5 Nothing is shared that was not declared -----------------


def test_a_task_sees_only_what_it_declared_it_needs() -> None:
    plan = plan_of("gather", "unrelated", "write", edges=((2, 0),))
    gather, unrelated, write = plan.tasks
    coordinator = WorkforceCoordinator(plan, baseline=SharedContext(facts=("the workspace",)))

    coordinator.record(
        gather.id,
        replace(
            gather,
            status=TaskStatus.COMPLETED,
            result=TaskResult(summary="eleven sources", artifacts=("sources.md",)),
        ),
    )
    coordinator.record(
        unrelated.id,
        replace(
            unrelated,
            status=TaskStatus.COMPLETED,
            result=TaskResult(summary="something else entirely"),
        ),
    )

    context = coordinator.context_for(write)

    assert "eleven sources" in " ".join(context.facts)
    assert "something else entirely" not in " ".join(context.facts)
    assert context.artifacts == ("sources.md",)
    assert "the workspace" in context.facts, "the manager's own baseline still reaches it"


def test_a_task_with_no_dependencies_gets_only_the_baseline() -> None:
    """Sharing is never the default: this is §86 as an assertion."""
    plan = plan_of("first", "second")
    first, second = plan.tasks
    coordinator = WorkforceCoordinator(plan, baseline=SharedContext(constraints=("be brief",)))
    coordinator.record(
        first.id,
        replace(first, status=TaskStatus.COMPLETED, result=TaskResult(summary="a finding")),
    )

    context = coordinator.context_for(second)

    assert context.facts == ()
    assert context.constraints == ("be brief",)


def test_a_failed_dependency_hands_nothing_down() -> None:
    plan = plan_of("gather", "write", edges=((1, 0),))
    gather, write = plan.tasks
    coordinator = WorkforceCoordinator(plan)
    coordinator.record(
        gather.id,
        replace(gather, status=TaskStatus.FAILED, result=TaskResult(summary="half of it")),
    )

    assert coordinator.context_for(write).facts == ()


def test_nothing_but_the_coordinator_builds_context_for_a_task() -> None:
    """12.5 as a rule about the source, not a rule people remember.

    An employee reaches another only through the coordinator, and the way that
    stays true is that the supervisor has no other way to make one.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = (root / "application" / "prometheus" / "supervisor.py").read_text(encoding="utf-8")
    built = source.count("SharedContext(")
    assert built == 1, "the only SharedContext() in the supervisor is the empty default"
    assert "context or SharedContext()" in source


# --- 12.7 Accepted on the evidence --------------------------------------------


def completed(**output) -> Task:
    return replace(
        Task.create("do it"),
        status=TaskStatus.COMPLETED,
        result=TaskResult(summary="All done!", output=output),
    )


def observation(succeeded: bool, *, refused: bool = False) -> dict:
    details = {"tool": "fs.write", **({"refused": True} if refused else {})}
    return {"summary": "x", "succeeded": succeeded, "details": details}


def test_a_success_with_every_tool_call_refused_is_not_accepted() -> None:
    taken = accept(completed(observations=[observation(False, refused=True)] * 3))

    assert not taken.accepted
    assert taken.refused, "somebody else may be allowed to, so it is worth reassigning"


def test_a_success_with_every_tool_call_failed_is_not_accepted() -> None:
    taken = accept(completed(observations=[observation(False), observation(False)]))

    assert not taken.accepted
    assert not taken.refused


def test_one_tool_call_that_worked_is_enough() -> None:
    taken = accept(completed(observations=[observation(False), observation(True)]))

    assert taken.accepted


def test_a_task_that_used_no_tools_is_accepted() -> None:
    """Judgement is real work. Requiring evidence of action would reject it."""
    assert accept(completed(observations=[])).accepted


async def test_a_refused_result_is_reassigned_rather_than_retried() -> None:
    from application.prometheus.supervisor import Recovery, TaskOutcome, recovery_for

    outcome = TaskOutcome(
        task=completed(observations=[observation(False, refused=True)]),
        employee="worker",
        acceptance=accept(completed(observations=[observation(False, refused=True)])),
    )

    assert not outcome.succeeded
    assert recovery_for(outcome) is Recovery.REASSIGN
