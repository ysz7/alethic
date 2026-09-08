"""Phase 14: connecting a service through the same door a window uses.

The whole flow over the real HTTP surface - add, connect, inspect, classify,
disable, enable, remove - against a real MCP server in a subprocess. What is
being asserted is not that the routes exist but that the interface carries
decisions rather than making them: it is *told* which capabilities need
approval, it cannot set that itself, and it can never read a credential back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.container import build_container
from app.config.settings import Settings
from app.ui.server import create_app
from infrastructure.persistence.models import Base
from infrastructure.persistence.session import create_engine
from tests.fakes.llm import FakeLLM

SERVER = Path(__file__).resolve().parents[1] / "fakes" / "mcp_server.py"


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        data_dir=tmp_path,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'alethic.db'}",
        workspace_dir=tmp_path / "workspace",
    )
    _create_schema(settings)
    # No model is called by any of this - connecting a server is not work - but
    # building the manager routes one, and the suite runs without a key.
    def build(resolved: Settings):
        container = build_container(resolved)
        container.llm_for = lambda *args, **kwargs: FakeLLM([])  # type: ignore[method-assign]
        return container

    with TestClient(create_app(settings, build=build)) as connected:
        yield connected


def _create_schema(settings: Settings) -> None:
    import asyncio

    async def create() -> None:
        engine = create_engine(settings.resolved_database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create())


def add(client, name: str = "notes") -> dict:
    response = client.post(
        "/api/integrations",
        json={
            "name": name,
            "configuration": {"command": sys.executable, "args": [str(SERVER)]},
            "capabilities": ["EMAIL"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_service_is_added_connected_and_inspected(client) -> None:
    added = add(client)
    assert added["status"] == "CONFIGURING"
    assert added["tool_count"] == 0, "adding does not start anything"

    connected = client.post(f"/api/integrations/{added['id']}/connect").json()

    assert connected["status"] == "READY"
    assert [tool["name"] for tool in connected["tools"]] == [
        "search_notes",
        "send_note",
        "unclassified_thing",
    ]
    assert connected["capabilities"] == ["EMAIL"]


def test_the_interface_is_told_what_needs_approval_and_does_not_work_it_out(
    client,
) -> None:
    """The rule from §10: React never decides whether an action is safe."""
    added = add(client)
    connected = client.post(f"/api/integrations/{added['id']}/connect").json()

    verdicts = {tool["name"]: tool for tool in connected["tools"]}

    assert verdicts["send_note"]["requires_approval"] is True
    assert verdicts["unclassified_thing"]["requires_approval"] is True
    assert verdicts["search_notes"]["classified"] is False


def test_classifying_changes_what_the_platform_says_about_a_capability(client) -> None:
    added = add(client)
    client.post(f"/api/integrations/{added['id']}/connect")

    classified = client.post(
        f"/api/integrations/{added['id']}/capabilities",
        json={"effects": {"search_notes": "READ", "send_note": "SEND"}},
    ).json()
    verdicts = {tool["name"]: tool for tool in classified["tools"]}

    assert verdicts["search_notes"]["requires_approval"] is False
    assert verdicts["search_notes"]["risk"] == "LOW"
    assert verdicts["send_note"]["requires_approval"] is True


def test_an_interface_cannot_set_the_risk_itself(client) -> None:
    """Only an effect is accepted; the risk follows from it (ADR 0010)."""
    added = add(client)
    client.post(f"/api/integrations/{added['id']}/connect")

    refused = client.post(
        f"/api/integrations/{added['id']}/capabilities",
        json={"effects": {"send_note": "LOW"}},
    )

    assert refused.status_code >= 400


def test_disabling_keeps_the_setup_and_enabling_needs_none(client) -> None:
    added = add(client)
    client.post(f"/api/integrations/{added['id']}/connect")

    disabled = client.post(f"/api/integrations/{added['id']}/disable").json()
    assert disabled["enabled"] is False
    assert disabled["usable"] is False
    assert disabled["tool_count"] == 3, "nothing about its setup was forgotten"

    enabled = client.post(f"/api/integrations/{added['id']}/enable").json()
    assert enabled["status"] == "READY"


def test_removing_it_and_asking_again(client) -> None:
    added = add(client)
    client.post(f"/api/integrations/{added['id']}/connect")

    assert client.delete(f"/api/integrations/{added['id']}").json() == {"removed": True}
    assert client.get("/api/integrations").json()["integrations"] == []
    assert client.get(f"/api/integrations/{added['id']}").status_code == 404


def test_two_services_of_one_name_are_refused_with_a_reason(client) -> None:
    add(client)

    refused = client.post(
        "/api/integrations",
        json={"name": "notes", "configuration": {"command": "x"}},
    )

    assert refused.status_code == 400
    assert "already connected" in refused.json()["detail"]


def test_a_capability_this_platform_does_not_know_is_refused_with_the_list(
    client,
) -> None:
    refused = client.post(
        "/api/integrations",
        json={"name": "crm", "configuration": {"command": "x"}, "capabilities": ["TELEPATHY"]},
    )

    assert refused.status_code == 400
    assert "EMAIL" in refused.json()["detail"], "it says what is available"


def test_a_server_that_will_not_start_is_a_status_not_a_stack_trace(client) -> None:
    added = client.post(
        "/api/integrations",
        json={"name": "broken", "configuration": {"command": "definitely-not-a-program"}},
    ).json()

    connected = client.post(f"/api/integrations/{added['id']}/connect")

    assert connected.status_code == 200
    assert connected.json()["status"] == "CONNECTION_FAILED"


def test_a_credential_goes_in_and_never_comes_back_out(client) -> None:
    """There is no route that reads one, and that is the assertion."""
    stored = client.post("/api/credentials", json={"name": "NOTES_TOKEN", "value": "s3cret"})

    assert stored.status_code == 201
    assert stored.json() == {"name": "NOTES_TOKEN", "stored": True}
    assert client.get("/api/credentials").status_code == 405
    assert "s3cret" not in client.get("/api/integrations").text
