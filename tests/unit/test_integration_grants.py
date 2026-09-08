"""Phase 14: a grant is per integration, and it can only add.

ADR 0015's second decision, as assertions. The employee declares `integrations:
[notes]` and never a tool name, because the names are not known when the file is
written and change when the server is updated - but what is *enforced* is still
a list of names, so least privilege is untouched.
"""

from __future__ import annotations

from dataclasses import replace

from domain.capabilities.models import Capability, CapabilityRequirement
from domain.employees.validation import Severity, check
from domain.integrations.grants import granted, missing
from domain.integrations.models import (
    DiscoveredTool,
    Integration,
    IntegrationStatus,
)
from infrastructure.employees.granting import GrantingEmployeeRegistry
from tests.fakes.employees import definition

TOOLS = (DiscoveredTool(name="search_notes"), DiscoveredTool(name="send_note"))


def notes(**extra) -> Integration:
    return Integration.create(
        "notes",
        status=IntegrationStatus.READY,
        discovered=TOOLS,
        granted_capabilities=frozenset({Capability.EMAIL}),
        **extra,
    )


class OneEmployee:
    """The smallest `EmployeeRegistry` there is."""

    def __init__(self, employee) -> None:
        self._employee = employee

    def list(self, workspace=None):
        return [self._employee]

    def get(self, name):
        return self._employee

    def find_by_capability(self, requirement):  # pragma: no cover - not used here
        return []


def researcher(**extra):
    """Declares the integration by name, never a tool of it."""
    employee = definition("researcher", tools=frozenset({"fs.read"}), **extra)
    return replace(employee, integrations=frozenset({"notes"}))


def test_a_grant_expands_into_the_names_the_registry_enforces() -> None:
    employee = granted(researcher(), [notes()])

    assert employee.allowed_tools == {"fs.read", "notes.search_notes", "notes.send_note"}


def test_only_an_integration_the_employee_named_is_granted() -> None:
    """Connected is not the same as granted: it has to be in the declaration."""
    employee = researcher()
    unnamed = Integration.create(
        "issues", status=IntegrationStatus.READY, discovered=(DiscoveredTool(name="open"),)
    )

    expanded = granted(employee, [notes(), unnamed])

    assert "notes.search_notes" in expanded.allowed_tools
    assert "issues.open" not in expanded.allowed_tools


def test_an_employee_granting_nothing_gains_nothing_from_a_connected_service() -> None:
    """The rejected ambient model: a connected integration is not ambient."""
    ungranted = definition("organizer", tools=frozenset({"fs.read"}))

    expanded = granted(ungranted, [notes()])

    assert expanded.allowed_tools == {"fs.read"}
    assert Capability.EMAIL not in expanded.capabilities


def test_a_grant_never_removes_what_the_employee_already_had() -> None:
    employee = researcher()

    expanded = granted(employee, [notes()])

    assert employee.allowed_tools <= expanded.allowed_tools


def test_a_disabled_integration_grants_nothing_and_is_not_an_error() -> None:
    employee = researcher()

    expanded = granted(employee, [notes().set_enabled(False)])

    assert expanded.allowed_tools == {"fs.read"}


def test_a_grant_brings_the_capability_that_makes_work_reach_the_employee() -> None:
    """Without this the manager never routes mail work to whoever has mail."""
    employee = granted(researcher(), [notes()])

    assert Capability.EMAIL in employee.capabilities
    assert employee.offers(CapabilityRequirement(required=frozenset({Capability.EMAIL})))


def test_an_integration_that_is_not_connected_here_is_a_warning_not_an_error() -> None:
    employee = researcher()
    issues = check(employee, {"fs.read": frozenset()}, integrations=())

    integration_issues = [i for i in issues if "notes" in i.message]
    assert [i.severity for i in integration_issues] == [Severity.WARNING]
    assert missing(employee, []) == {"notes"}


def test_the_registry_hands_out_employees_with_their_grants_applied() -> None:
    registry = GrantingEmployeeRegistry(OneEmployee(researcher()), [notes()])

    assert "notes.search_notes" in registry.get("researcher").allowed_tools
    assert "notes.search_notes" in registry.list()[0].allowed_tools


def test_the_manager_can_find_an_employee_by_what_its_grant_gave_it() -> None:
    registry = GrantingEmployeeRegistry(OneEmployee(researcher()), [notes()])

    found = registry.find_by_capability(
        CapabilityRequirement(required=frozenset({Capability.EMAIL}))
    )

    assert [employee.name for employee in found] == ["researcher"]


def test_removing_the_integration_takes_the_grant_away_from_the_next_run() -> None:
    registry = GrantingEmployeeRegistry(OneEmployee(researcher()), [notes()])

    registry.refresh([])

    assert registry.get("researcher").allowed_tools == {"fs.read"}
