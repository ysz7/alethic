"""Phase 14: adding, connecting, switching off and removing a service.

Against the real `IntegrationService` and the real `InMemoryToolRegistry`, with
a connector that answers instantly - the protocol itself is exercised in
`tests/integration/test_mcp_server.py` against a real subprocess, and repeating
it here would only make these slower.
"""

from __future__ import annotations

import pytest

from application.integrations.service import IntegrationService
from domain.capabilities.models import Capability
from domain.errors import (
    DuplicateIntegrationError,
    IntegrationAuthenticationError,
    IntegrationNotFoundError,
    IntegrationUnavailableError,
)
from domain.integrations.models import (
    DiscoveredTool,
    Integration,
    IntegrationStatus,
)
from domain.integrations.protocols import Connection
from domain.integrations.specs import spec_for
from domain.policies.models import RiskLevel
from domain.policies.risk import Effect
from domain.secrets.models import Secret
from infrastructure.persistence.integration_repository import (
    InMemoryIntegrationRepository,
)
from infrastructure.tools.registry import InMemoryToolRegistry
from tests.fakes.actors import user

TOOLS = (DiscoveredTool(name="search_notes"), DiscoveredTool(name="send_note"))


class FakeTool:
    """Implements `domain.tools.protocols.Tool`."""

    def __init__(self, spec) -> None:
        self.spec = spec

    async def execute(self, input_data):  # pragma: no cover - never called here
        raise NotImplementedError


class Connector:
    """A connector the test drives, and a record of what it was asked."""

    def __init__(self, *, fails: Exception | None = None) -> None:
        self._fails = fails
        self.environments: list[dict[str, str]] = []
        self.closed = 0

    async def __call__(self, integration: Integration, environment) -> Connection:
        self.environments.append(environment)
        if self._fails is not None:
            raise self._fails
        ready = integration.rediscovered(TOOLS)

        def close() -> None:
            self.closed += 1

        return Connection(
            integration=ready,
            tools=tuple(FakeTool(spec_for(ready, tool)) for tool in TOOLS),
            close=close,
        )


class Secrets:
    """Implements `domain.secrets.protocols.SecretResolver`."""

    def __init__(self, **values: str) -> None:
        self._values = values

    def maybe(self, name):
        value = self._values.get(name)
        return Secret(name=name, _value=value) if value else None

    def get(self, name):  # pragma: no cover - the service only ever asks maybe
        raise NotImplementedError


@pytest.fixture
def parts():
    repository = InMemoryIntegrationRepository()
    registry = InMemoryToolRegistry()
    connector = Connector()
    changes: list[list[Integration]] = []
    service = IntegrationService(
        repository,
        registry,
        connector,
        secrets=Secrets(NOTES_TOKEN="s3cret"),
        on_change=changes.append,
    )
    return service, registry, connector, changes


async def added(service, **extra) -> Integration:
    return await service.add(
        "notes",
        {"command": "python", "args": ["server.py"]},
        secret_names=("NOTES_TOKEN",),
        capabilities=frozenset({Capability.EMAIL}),
        **extra,
    )


# --- Adding and connecting ----------------------------------------------------


async def test_adding_records_it_without_running_anything(parts) -> None:
    """A server that will not start still leaves a record the user can correct."""
    service, registry, connector, _ = parts

    integration = await added(service)

    assert integration.status is IntegrationStatus.CONFIGURING
    assert connector.environments == [], "adding must not start a program"
    assert registry.list_specs(user("*")) == []


async def test_connecting_discovers_and_registers(parts) -> None:
    service, registry, _, _ = parts
    integration = await added(service)

    connected = await service.connect(integration.id)

    assert connected.status is IntegrationStatus.READY
    assert [tool.name for tool in connected.discovered] == ["search_notes", "send_note"]
    assert {spec.name for spec in registry.list_specs(user("*"))} == {
        "notes.search_notes",
        "notes.send_note",
    }


async def test_two_integrations_of_one_name_are_refused(parts) -> None:
    """Otherwise `notes.send_note` names two different actions."""
    service, _, _, _ = parts
    await added(service)

    with pytest.raises(DuplicateIntegrationError):
        await added(service)


async def test_the_credentials_reach_the_server_and_nothing_else(parts) -> None:
    service, _, connector, _ = parts
    integration = await added(service)

    connected = await service.connect(integration.id)

    assert connector.environments == [{"NOTES_TOKEN": "s3cret"}]
    assert "s3cret" not in str(connected), "the value is not on the record"


async def test_a_secret_that_is_not_set_is_left_out_rather_than_sent_empty(parts) -> None:
    service, _, connector, _ = parts
    integration = await service.add("other", {"command": "x"}, secret_names=("ABSENT",))

    await service.connect(integration.id)

    assert connector.environments == [{}]


# --- The ways connecting fails ------------------------------------------------


async def test_a_server_that_will_not_start_becomes_a_status_not_an_exception() -> None:
    repository, registry = InMemoryIntegrationRepository(), InMemoryToolRegistry()
    service = IntegrationService(
        repository, registry, Connector(fails=IntegrationUnavailableError("no such program"))
    )
    integration = await service.add("notes", {"command": "nope"})

    failed = await service.connect(integration.id)

    assert failed.status is IntegrationStatus.CONNECTION_FAILED
    assert await repository.get(integration.id) == failed


async def test_a_rejected_credential_says_so_specifically() -> None:
    """A different answer from a wrong command: this one needs a new secret."""
    service = IntegrationService(
        InMemoryIntegrationRepository(),
        InMemoryToolRegistry(),
        Connector(fails=IntegrationAuthenticationError("token revoked")),
    )
    integration = await service.add("notes", {"command": "x"})

    failed = await service.connect(integration.id)

    assert failed.status is IntegrationStatus.AUTHENTICATION_REQUIRED


async def test_asking_about_something_that_is_not_here(parts) -> None:
    service, _, _, _ = parts
    from uuid import uuid4

    with pytest.raises(IntegrationNotFoundError):
        await service.get(uuid4())


# --- Turning off and removing -------------------------------------------------


async def test_disabling_takes_the_tools_away_and_keeps_the_setup(parts) -> None:
    service, registry, connector, _ = parts
    integration = await added(service)
    await service.connect(integration.id)

    disabled = await service.disable(integration.id)

    assert registry.list_specs(user("*")) == [], "no stale tools left behind"
    assert connector.closed == 1, "the server it started was stopped"
    assert not disabled.enabled
    assert disabled.configuration == {"command": "python", "args": ["server.py"]}
    assert disabled.discovered == TOOLS


async def test_enabling_again_needs_no_setup(parts) -> None:
    service, registry, _, _ = parts
    integration = await added(service)
    await service.connect(integration.id)
    await service.disable(integration.id)

    enabled = await service.enable(integration.id)

    assert enabled.status is IntegrationStatus.READY
    assert len(registry.list_specs(user("*"))) == 2


async def test_removing_leaves_no_tool_behind(parts) -> None:
    service, registry, connector, _ = parts
    integration = await added(service)
    await service.connect(integration.id)

    assert await service.remove(integration.id) is True
    assert registry.list_specs(user("*")) == []
    assert connector.closed == 1
    assert await service.list() == []


async def test_removing_something_never_connected_still_cleans_up(parts) -> None:
    """The case that matters: this process never had the live connection."""
    service, registry, _, _ = parts
    integration = await added(service)
    await service.connect(integration.id)
    second = IntegrationService(
        InMemoryIntegrationRepository(), registry, Connector()
    )

    # A different process's view: the tools are registered, nothing is live.
    await second._repository.save(await service.get(integration.id))
    await second.remove(integration.id)

    assert registry.list_specs(user("*")) == []


# --- Classification and restart -----------------------------------------------


async def test_classifying_a_tool_changes_the_risk_of_the_registered_tool(parts) -> None:
    """Storing a new effect without rebuilding would leave the old one in force."""
    service, registry, _, _ = parts
    integration = await added(service)
    await service.connect(integration.id)
    before = {spec.name: spec.risk_level for spec in registry.list_specs(user("*"))}

    await service.classify(integration.id, {"search_notes": Effect.READ})
    after = {spec.name: spec.risk_level for spec in registry.list_specs(user("*"))}

    assert before["notes.search_notes"] is RiskLevel.HIGH, "unclassified asks"
    assert after["notes.search_notes"] is RiskLevel.LOW
    assert after["notes.send_note"] is RiskLevel.HIGH, "the other one is untouched"


async def test_a_restarted_process_offers_what_was_stored_without_reconnecting(
    parts,
) -> None:
    service, _registry, _connector, _ = parts
    integration = await added(service)
    await service.connect(integration.id)

    fresh_registry = InMemoryToolRegistry()
    fresh = IntegrationService(service._repository, fresh_registry, Connector())
    restored = await fresh.restore()

    assert restored == 1
    assert len(fresh_registry.list_specs(user("*"))) == 2


async def test_a_disabled_integration_is_not_restored(parts) -> None:
    service, _, _, _ = parts
    integration = await added(service)
    await service.connect(integration.id)
    await service.disable(integration.id)

    fresh_registry = InMemoryToolRegistry()
    fresh = IntegrationService(service._repository, fresh_registry, Connector())

    assert await fresh.restore() == 0
    assert fresh_registry.list_specs(user("*")) == []


async def test_every_change_is_announced_so_grants_can_follow(parts) -> None:
    """The employee registry's snapshot is refreshed from this, never polled."""
    service, _, _, changes = parts
    integration = await added(service)
    await service.connect(integration.id)
    await service.disable(integration.id)

    assert len(changes) == 3
    assert changes[-1][0].enabled is False
