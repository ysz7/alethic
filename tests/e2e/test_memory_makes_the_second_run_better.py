"""Phase 9's validation: the same work, asked for twice, goes better the second time.

The first run has to find out where the sales figures are, and spends a tool
call and a step doing it. The second run is given the same goal, and what the
first learned is in front of it before it plans - so it answers without going
looking again.

Everything here is real except the model and the clock: a real SQLite file with
the real FTS5 index behind it, the real runtime, the real recorder. What is
asserted is what the phase promises - that the second run *knew* something the
first had to discover, and that memory survived the process that wrote it.
"""

from __future__ import annotations

from pathlib import Path

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.employee_runtime.executor import Executor
from application.employee_runtime.planner import Planner
from application.employee_runtime.runtime import EmployeeRuntime, RuntimeDependencies
from application.employee_runtime.verifier import Verifier
from application.memory.assembler import ContextAssembler
from application.memory.recorder import MemoryRecorder
from domain.employees.limits import ExecutionLimits
from domain.llm.models import ToolCallRequest
from domain.memory.models import MemoryQuery
from domain.tasks.task import Task, TaskStatus
from domain.tools.models import ToolResult
from infrastructure.memory.sqlite import SqliteMemory
from infrastructure.persistence.in_memory_task_repository import InMemoryTaskRepository
from infrastructure.persistence.models import Base
from infrastructure.persistence.session import create_engine, create_session_factory
from infrastructure.tools.registry import InMemoryToolRegistry
from tests.fakes.employees import definition
from tests.fakes.llm import FakeLLM, reply, tool_reply
from tests.fakes.tools import FakeTool

GOAL = "Report the sales figures for the quarter"
PLAN = reply('{"steps": [{"description": "Find the figures", "expected_outcome": "a number"}]}')
PASS = reply('{"passed": true, "reason": "the figures are there"}')
ANSWER = "Sales were 412,000 for the quarter; the figures are in finance/sales-q3.csv."


@pytest_asyncio.fixture
async def store(tmp_path: Path):
    """A real database file: memory that did not survive one is not memory."""
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'memory.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield create_session_factory(engine)
    await engine.dispose()


def build(script, memory, tool):
    llm = FakeLLM(script)
    registry = InMemoryToolRegistry([tool])
    tasks = InMemoryTaskRepository()
    employee = definition("analyst", tools=frozenset({tool.spec.name}))
    return (
        EmployeeRuntime(
            employee,
            RuntimeDependencies(
                planner=Planner(llm),
                executor=Executor(llm, registry, limits=ExecutionLimits()),
                verifier=Verifier(llm),
                tasks=tasks,
                tools=registry,
                limits=ExecutionLimits(),
                context=ContextAssembler(memory),
                recorder=MemoryRecorder(memory),
            ),
        ),
        tasks,
        llm,
    )


async def test_the_second_run_starts_from_what_the_first_learned(
    store: async_sessionmaker[AsyncSession],
) -> None:
    memory = SqliteMemory(store)
    tool = FakeTool("fs.read", result=ToolResult.ok(value="412,000"))

    # --- The first run: it has to go and look --------------------------------
    first, tasks, first_llm = build(
        [
            PLAN,
            tool_reply(ToolCallRequest(id="c1", name="fs.read", arguments={"path": "sales"})),
            reply(ANSWER),
            PASS,
        ],
        memory,
        tool,
    )
    task = Task.create(GOAL)
    await tasks.save(task)
    await first.run(task)

    assert (await tasks.get(task.id)).status is TaskStatus.COMPLETED
    assert tool.calls, "the first run had to open the file to find out"

    # --- The second run: the same goal, a new process ------------------------
    # A second adapter over the same file, and a second runtime that shares
    # nothing with the first but the database.
    second, later_tasks, second_llm = build(
        [PLAN, reply(ANSWER), PASS], SqliteMemory(store), FakeTool("fs.read")
    )
    repeat = Task.create(GOAL)
    await later_tasks.save(repeat)
    await second.run(repeat)

    assert (await later_tasks.get(repeat.id)).status is TaskStatus.COMPLETED

    planning = "\n".join(m.content for m in second_llm.requests[0].messages)
    execution = "\n".join(m.content for m in second_llm.requests[1].messages)
    assert "sales-q3.csv" in execution, "the second run was told what the first found out"
    assert "sales-q3.csv" in planning, "and knew it before it planned, not after"
    assert "412,000" in execution

    # And the first run was told nothing, because there was nothing to tell.
    assert "sales-q3.csv" not in "\n".join(m.content for m in first_llm.requests[0].messages)


async def test_what_is_remembered_is_the_outcome_not_the_transcript(
    store: async_sessionmaker[AsyncSession],
) -> None:
    """Memory is a pointer to what happened; the task row holds the whole of it."""
    memory = SqliteMemory(store)
    tool = FakeTool("fs.read", result=ToolResult.ok(value="412,000"))
    runtime, tasks, _ = build(
        [
            PLAN,
            tool_reply(ToolCallRequest(id="c1", name="fs.read", arguments={"path": "sales"})),
            reply(ANSWER),
            PASS,
        ],
        memory,
        tool,
    )
    task = Task.create(GOAL)
    await tasks.save(task)
    await runtime.run(task)

    remembered = await memory.recall(MemoryQuery(text=GOAL, limit=20))

    assert remembered, "something was kept"
    assert all(len(item.content) <= 1000 for item in remembered)
    assert not any("Step 1" in item.content for item in remembered), (
        "working notes are private to the employee, not workspace memory"
    )
