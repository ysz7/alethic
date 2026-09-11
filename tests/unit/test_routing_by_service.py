"""Routing work to whoever holds the connected service.

Phase 18's finding, and the reason it is a finding rather than an opinion:
`use-a-connected-service` failed four times out of four with the analyst
searching somebody's notes by running a Python script, being refused, and
reporting honestly that it could not. The refusal was right and the routing put
it there. `Capability` is a closed vocabulary and every term in it is already
claimed by an employee the platform ships with, so the notes server could only
declare FILE_ACCESS - which is also what reading a file needs, and what four of
the five employees offer.

So a task can now ask for a service by name as well as for an ability, and
these are the rules that keeps it from becoming a way to route work nowhere.
"""

from __future__ import annotations

import json
from uuid import uuid4

from application.prometheus.delegation import CapabilityDelegator
from application.prometheus.planner import ObjectivePlanner
from application.prometheus.workforce import describe
from domain.capabilities.models import Capability, CapabilityRequirement
from domain.tasks.task import Task
from domain.workforce.protocols import Objective
from domain.workforce.routing import Requirement, holders
from tests.fakes.employees import definition
from tests.fakes.llm import FakeLLM, reply
from tests.fakes.workforce import FakeRegistry

FILES = frozenset({Capability.FILE_ACCESS})

ANALYST = definition(
    "analyst", tools=frozenset({"fs.read", "code.run"}), capabilities=FILES
)
ASSISTANT = definition(
    "assistant",
    tools=frozenset({"fs.read", "notes.search_notes"}),
    capabilities=FILES,
    integrations=frozenset({"notes"}),
)


async def planned(request: str, tasks: list[dict], workforce: list) -> object:
    """The plan a model returning exactly these tasks would produce."""
    llm = FakeLLM([reply(json.dumps({"rationale": "", "tasks": tasks}))])
    return await ObjectivePlanner(llm).plan(Objective(id=uuid4(), text=request), workforce)


# --- The rule itself ----------------------------------------------------------


def test_a_service_narrows_to_the_people_granted_it() -> None:
    assert [d.name for d in holders([ANALYST, ASSISTANT], ["notes"])] == ["assistant"]


def test_naming_no_service_narrows_nothing() -> None:
    assert len(holders([ANALYST, ASSISTANT], [])) == 2


def test_a_service_nobody_holds_leaves_an_empty_field() -> None:
    """Which the delegator reads as "widen back", never as "fail the task"."""
    assert holders([ANALYST, ASSISTANT], ["gmail"]) == []


def test_holding_one_of_two_named_services_is_not_enough() -> None:
    assert holders([ASSISTANT], ["notes", "gmail"]) == []


# --- What the planner may write into `needs` ----------------------------------


async def test_a_service_name_survives_only_because_somebody_holds_it() -> None:
    plan = await planned(
        "Search my notes for shipping",
        [{"id": "t1", "goal": "Search the notes", "needs": ["notes"]}],
        [ANALYST, ASSISTANT],
    )

    requirement = plan.requirements[plan.tasks[0].id]
    assert requirement.services == frozenset({"notes"})
    assert not requirement.capabilities.required


async def test_an_invented_service_is_dropped_like_an_invented_capability() -> None:
    plan = await planned(
        "Search my notes for shipping",
        [{"id": "t1", "goal": "Search the notes", "needs": ["telepathy"]}],
        [ANALYST, ASSISTANT],
    )

    assert plan.tasks[0].id not in plan.requirements


async def test_the_two_kinds_of_term_are_read_from_one_list() -> None:
    plan = await planned(
        "Search my notes and write it up",
        [{"id": "t1", "goal": "Search the notes", "needs": ["FILE_ACCESS", "notes"]}],
        [ANALYST, ASSISTANT],
    )

    requirement = plan.requirements[plan.tasks[0].id]
    assert requirement.capabilities.required == FILES
    assert requirement.services == frozenset({"notes"})


# --- What the delegator does with it ------------------------------------------


async def test_the_service_decides_where_a_shared_capability_could_not() -> None:
    """The whole finding, in one test: FILE_ACCESS leaves two, the service one."""
    llm = FakeLLM()  # a field of one is never put to a model
    delegator = CapabilityDelegator(llm, FakeRegistry(ANALYST, ASSISTANT))

    chosen, _, reason = await delegator.choose(
        Task.create("Search the notes for what we said about shipping"),
        requirement=Requirement(
            capabilities=CapabilityRequirement(required=FILES),
            services=frozenset({"notes"}),
        ),
    )

    assert chosen.name == "assistant"
    assert llm.call_count == 0
    assert "notes" in reason


async def test_a_service_nobody_holds_widens_back_rather_than_failing() -> None:
    llm = FakeLLM([reply(json.dumps({"employee": "analyst", "reason": "closest fit"}))])
    delegator = CapabilityDelegator(llm, FakeRegistry(ANALYST, ASSISTANT))

    chosen, _, _ = await delegator.choose(
        Task.create("Look it up"),
        requirement=Requirement(services=frozenset({"gmail"})),
    )

    assert chosen.name == "analyst"


# --- Where the planner learns the names ---------------------------------------


def test_the_card_names_the_services_so_a_plan_can_ask_for_one() -> None:
    """A term the model cannot see is a term it cannot write into `needs`."""
    assert "Connected services they hold: notes" in describe([ASSISTANT])
    assert "Connected services" not in describe([ANALYST])
