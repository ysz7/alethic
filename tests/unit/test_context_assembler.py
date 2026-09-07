"""What a run is told, and where each part of it came from (§9.6)."""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from application.employee_runtime.executor import Executor
from application.employee_runtime.planner import Planner
from application.employee_runtime.runtime import EmployeeRuntime, RuntimeDependencies
from application.employee_runtime.verifier import Verifier
from application.memory.assembler import ContextAssembler
from application.memory.recorder import MemoryRecorder
from domain.employees.limits import ExecutionLimits
from domain.memory.models import MemoryItem, MemoryKind, MemoryQuery, MemoryScope
from domain.tasks.task import Task, TaskStatus
from domain.workforce.assignment import SharedContext
from infrastructure.memory.in_memory import InMemoryMemory
from infrastructure.persistence.in_memory_task_repository import InMemoryTaskRepository
from infrastructure.tools.registry import InMemoryToolRegistry
from tests.fakes.employees import definition
from tests.fakes.llm import FakeLLM, reply

PLAN = reply('{"steps": [{"description": "Answer it", "expected_outcome": "an answer"}]}')
PASS = reply('{"passed": true, "reason": "good enough"}')


def build(script, memory=None, employee=None):
    llm = FakeLLM(script)
    registry = InMemoryToolRegistry([])
    tasks = InMemoryTaskRepository()
    who = employee or definition()
    deps = RuntimeDependencies(
        planner=Planner(llm),
        executor=Executor(llm, registry, limits=ExecutionLimits()),
        verifier=Verifier(llm),
        tasks=tasks,
        tools=registry,
        limits=ExecutionLimits(),
        context=ContextAssembler(memory) if memory else None,
        recorder=MemoryRecorder(memory) if memory else None,
    )
    return EmployeeRuntime(who, deps), tasks, llm


async def test_the_three_parts_arrive_in_order_of_trust() -> None:
    memory = InMemoryMemory()
    employee = definition()
    await memory.remember(
        MemoryItem.create(
            "The invoices live in finance/2026",
            scope=MemoryScope.WORKSPACE,
            kind=MemoryKind.SEMANTIC,
        )
    )
    task = Task.create("Sort the invoices")

    assembled = await ContextAssembler(memory).assemble(
        task,
        employee,
        SharedContext(facts=("Last month's are already done",), constraints=("Keep names",)),
    )

    assert assembled.goal == task.goal
    assert assembled.facts == ("Last month's are already done",)
    assert assembled.constraints == ("Keep names",)
    assert assembled.recollections() == ("The invoices live in finance/2026",)


async def test_what_is_remembered_reaches_the_model_as_recollection() -> None:
    """Not as fact: memory can be stale in a way an assignment cannot."""
    memory = InMemoryMemory()
    await memory.remember(
        MemoryItem.create(
            "The quarterly report is in reports/q3.md",
            scope=MemoryScope.WORKSPACE,
            kind=MemoryKind.SEMANTIC,
        )
    )
    runtime, tasks, llm = build([PLAN, reply("Found it."), PASS], memory=memory)
    task = Task.create("Find the quarterly report")
    await tasks.save(task)

    await runtime.run(task)

    execution = llm.requests[1]  # 0 is planning, 1 is the first execution turn
    prompt = "\n".join(message.content for message in execution.messages)
    assert "reports/q3.md" in prompt
    assert "may be out of date" in prompt or "confirm" in prompt


async def test_a_runtime_without_memory_is_the_runtime_it_was_before() -> None:
    runtime, tasks, llm = build([PLAN, reply("An answer."), PASS])
    task = Task.create("Explain something")
    await tasks.save(task)

    await runtime.run(task)

    prompt = "\n".join(m.content for m in llm.requests[1].messages)
    assert "remember" not in prompt.lower()
    assert (await tasks.get(task.id)).status is TaskStatus.COMPLETED


async def test_a_run_writes_down_what_became_of_it() -> None:
    memory = InMemoryMemory()
    runtime, tasks, _ = build([PLAN, reply("Twelve invoices, all filed."), PASS], memory=memory)
    task = Task.create("File the invoices")
    await tasks.save(task)

    await runtime.run(task)

    remembered = await memory.recall(MemoryQuery(text="invoices"))
    assert any("Twelve invoices" in found.content for found in remembered)


async def test_an_employee_recalls_its_own_notes_and_not_a_colleagues() -> None:
    memory = InMemoryMemory()
    mine = definition("mine")
    theirs = definition("theirs")
    for who, note in ((mine, "I always start with fs.list"), (theirs, "I never use fs.list")):
        await memory.remember(
            MemoryItem.create(
                note,
                scope=MemoryScope.EMPLOYEE_PRIVATE,
                kind=MemoryKind.SEMANTIC,
                employee_id=who.id,
            )
        )

    assembled = await ContextAssembler(memory).assemble(Task.create("Use fs.list"), mine)

    assert assembled.recollections() == ("I always start with fs.list",)


async def test_a_recall_that_fails_leaves_the_run_with_what_it_was_told() -> None:
    class Broken:
        async def remember(self, item): ...

        async def recall(self, query):
            raise RuntimeError("the index is corrupt")

    assembled = await ContextAssembler(Broken()).assemble(
        Task.create("Do the work"),
        definition(),
        SharedContext(facts=("This still arrives",)),
    )

    assert assembled.recalled == ()
    assert assembled.facts == ("This still arrives",)


async def test_a_narrowed_assignment_still_carries_its_facts_into_memory_recall() -> None:
    """The assignment is part of the query, not just part of the prompt."""
    memory = InMemoryMemory()
    employee = definition()
    await memory.remember(
        MemoryItem.create(
            "Ledger exports are tab separated",
            scope=MemoryScope.WORKSPACE,
            kind=MemoryKind.SEMANTIC,
        )
    )
    task = Task.create("Clean up the export")

    assembled = await ContextAssembler(memory).assemble(
        task,
        employee,
        SharedContext(facts=("It is a ledger export",)),
    )

    assert assembled.recollections() == ("Ledger exports are tab separated",)


async def test_a_plans_memory_follows_the_plan_and_not_the_employee() -> None:
    memory = InMemoryMemory()
    plan_id = uuid4()
    await memory.remember(
        MemoryItem.create(
            "Step one produced sources.csv",
            scope=MemoryScope.PLAN,
            kind=MemoryKind.EPISODIC,
            plan_id=plan_id,
        )
    )
    task = Task.create("Summarise the sources")
    within_plan = replace(task, plan_id=plan_id)
    outside_plan = replace(task, plan_id=uuid4())

    assembler = ContextAssembler(memory)
    assert (await assembler.assemble(within_plan, definition())).recollections() == (
        "Step one produced sources.csv",
    )
    assert (await assembler.assemble(outside_plan, definition())).recollections() == ()
