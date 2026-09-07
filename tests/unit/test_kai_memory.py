"""What the manager remembers, and what it hands down (§9.4).

KAI's half of memory is a different grain from an employee's: what it reads out
of a request - how the user wants work done here - outlives the request, and
what the workspace already knows travels to the tasks it delegates rather than
staying in the manager's own head.
"""

from __future__ import annotations

from application.memory.recorder import MemoryRecorder
from application.memory.workspace import WorkspaceMemory
from domain.memory.models import MemoryItem, MemoryKind, MemoryQuery, MemoryScope
from domain.workforce.protocols import ObjectiveStatus
from infrastructure.memory.in_memory import InMemoryMemory
from tests.fakes.llm import FakeLLM, reply
from tests.unit.test_kai_manager import build, intent, plan, verdict


def workspace_memory(memory: InMemoryMemory) -> WorkspaceMemory:
    return WorkspaceMemory(memory, MemoryRecorder(memory))


async def test_a_preference_stated_in_passing_is_kept() -> None:
    memory = InMemoryMemory()
    manager, _, _, _ = build(
        script=[
            intent(preferences=["always answer in Markdown"]),
            plan("Write the summary"),
            verdict(True),
            "Written.",
        ],
        memory=workspace_memory(memory),
    )

    await manager.handle_objective(await manager.receive("Summarise the notes"))

    kept = await memory.recall(MemoryQuery(kinds=frozenset({MemoryKind.SEMANTIC})))
    assert any("Markdown" in item.content for item in kept)
    assert all(item.expires_at is None for item in kept), "a preference has no expiry"


async def test_this_requests_own_parameters_are_not_remembered_as_preferences() -> None:
    """The finding from the first validation run, as a test.

    "The sales folder" is where this job is, not how every job should be done.
    Kept as a standing preference it comes back as a workspace fact and points
    the next request at the last one's folder - which is what happened, and cost
    an objective.
    """
    memory = InMemoryMemory()
    manager, _, _, _ = build(
        script=[
            intent(constraints={"input_location": "sales folder", "output_file": "summary.md"}),
            plan("Summarise the sales folder"),
            verdict(True),
            "Summarised.",
        ],
        memory=workspace_memory(memory),
    )

    await manager.handle_objective(await manager.receive("Summarise the sales folder"))

    kept = await memory.recall(MemoryQuery(kinds=frozenset({MemoryKind.SEMANTIC}), limit=20))
    assert not any("sales" in item.content for item in kept), (
        "a constraint on this request is not a standing preference"
    )


async def test_what_the_workspace_knows_is_handed_down_with_the_work() -> None:
    """Not kept for the manager: it reaches the employee the way facts do."""
    memory = InMemoryMemory()
    await memory.remember(
        MemoryItem.create(
            "The notes live in notes/2026",
            scope=MemoryScope.WORKSPACE,
            kind=MemoryKind.SEMANTIC,
        )
    )
    manager, execution, _, _ = build(
        script=[intent(), plan("Read the notes"), verdict(True), "Read them."],
        memory=workspace_memory(memory),
    )

    await manager.handle_objective(await manager.receive("Tell me what the notes say"))

    _, assignment = execution.started[0]
    assert "The notes live in notes/2026" in assignment.context.facts


async def test_a_question_answered_directly_is_still_on_the_record() -> None:
    """No task ran, so nothing else would have kept it."""
    memory = InMemoryMemory()
    manager, execution, _, _ = build(
        script=[intent(needs_work=False, answer="It is 41.")],
        memory=workspace_memory(memory),
    )

    result = await manager.handle_objective(await manager.receive("What is six times seven?"))

    assert result.status is ObjectiveStatus.DONE
    assert execution.started == []
    kept = await memory.recall(MemoryQuery(text="six times seven"))
    assert kept and "It is 41." in kept[0].content


async def test_a_manager_without_memory_behaves_exactly_as_it_did() -> None:
    manager, execution, _, _ = build(
        script=[intent(), plan("Read the notes"), verdict(True), "Read them."]
    )

    result = await manager.handle_objective(await manager.receive("Read the notes"))

    assert result.status is ObjectiveStatus.DONE
    _, assignment = execution.started[0]
    assert assignment.context.facts == ()


async def test_the_manager_plans_from_what_the_workspace_knows() -> None:
    """A request that leans on the last one is resolved, not investigated.

    The planner used to be the one stage that could not see memory: recalled
    context reached the employees and not the decomposition. Given "do the same
    again", it wrote a task to go and find out what "the same" had been - an
    entire employee run spent on archaeology. This is that gap, closed.
    """
    memory = InMemoryMemory()
    await memory.remember(
        MemoryItem.create(
            "The sales folder holds two Q3 CSVs and a README; summary.md documents them.",
            scope=MemoryScope.WORKSPACE,
            kind=MemoryKind.EPISODIC,
        )
    )
    llm = FakeLLM(
        [
            reply(item)
            for item in (intent(), plan("Summarise the returns folder"), verdict(True), "Done.")
        ]
    )
    manager, _, _, _ = build(script=[], llm=llm, memory=workspace_memory(memory))

    await manager.handle_objective(await manager.receive("Do the same for the returns folder."))

    # The first call is the reading of the request, the second the plan.
    for stage, request in (("the reading", llm.requests[0]), ("the plan", llm.requests[1])):
        prompt = "\n".join(message.content for message in request.messages)
        assert "summary.md documents them" in prompt, f"{stage} was made without memory"
