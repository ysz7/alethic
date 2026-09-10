"""Phase 14: a connected service survives a restart, and keeps no credential.

A real SQLite file on `tmp_path`, like every other repository test here, because
surviving a restart is the point and an in-memory database cannot show it.
"""

from __future__ import annotations

import json
from uuid import uuid4

from domain.capabilities.models import Capability
from domain.integrations.models import (
    DiscoveredTool,
    Integration,
    IntegrationKind,
    IntegrationStatus,
)
from domain.policies.risk import Effect
from infrastructure.persistence.integration_repository import (
    SqlIntegrationRepository,
)

TOOLS = (
    DiscoveredTool(
        name="search_notes",
        description="Search the notes.",
        json_schema={"type": "object", "properties": {"query": {"type": "string"}}},
    ),
    DiscoveredTool(name="send_note", description="Send a note."),
)


def notes(**extra) -> Integration:
    return Integration.create(
        "notes",
        kind=IntegrationKind.MCP,
        status=IntegrationStatus.READY,
        configuration={"command": "python", "args": ["server.py"]},
        effects={"search_notes": Effect.READ, "send_note": Effect.SEND},
        granted_capabilities=frozenset({Capability.EMAIL}),
        secret_names=("NOTES_TOKEN",),
        discovered=TOOLS,
        **extra,
    )


async def test_an_integration_comes_back_exactly_as_it_was_stored(session_factory) -> None:
    repository = SqlIntegrationRepository(session_factory)
    stored = notes()

    await repository.save(stored)
    loaded = await repository.get(stored.id)

    assert loaded == stored


async def test_what_it_offers_is_read_back_without_starting_it(session_factory) -> None:
    """The cache is the point: discovery must not be a prerequisite for listing."""
    repository = SqlIntegrationRepository(session_factory)
    await repository.save(notes())

    loaded = await repository.by_name("notes")

    assert loaded is not None
    assert [tool.name for tool in loaded.discovered] == ["search_notes", "send_note"]
    assert loaded.discovered[0].json_schema["properties"] == {"query": {"type": "string"}}
    assert loaded.tool_names == {"notes.search_notes", "notes.send_note"}


async def test_the_local_classification_survives_the_round_trip(session_factory) -> None:
    repository = SqlIntegrationRepository(session_factory)
    await repository.save(notes())

    loaded = await repository.by_name("notes")

    assert loaded is not None
    assert loaded.effect_for("send_note") is Effect.SEND
    assert loaded.effect_for("never_classified") is Effect.EXECUTE


async def test_an_effect_that_is_no_longer_a_known_label_falls_back_to_asking(
    session_factory,
) -> None:
    """A stale label must not make a whole integration unloadable."""
    repository = SqlIntegrationRepository(session_factory)
    stored = notes()
    await repository.save(stored)
    async with session_factory() as session:
        from sqlalchemy import text

        await session.execute(
            text("UPDATE integrations SET effects = :effects WHERE id = :id"),
            {"effects": json.dumps({"send_note": "TELEPORT"}), "id": str(stored.id)},
        )
        await session.commit()

    loaded = await repository.get(stored.id)

    assert loaded is not None
    assert loaded.effect_for("send_note") is Effect.EXECUTE


async def test_no_credential_is_written_to_the_row(session_factory) -> None:
    """Only the names of the secrets. §74."""
    repository = SqlIntegrationRepository(session_factory)
    await repository.save(notes())

    async with session_factory() as session:
        from sqlalchemy import text

        row = (await session.execute(text("SELECT * FROM integrations"))).mappings().one()

    # The name, and not the value - asserted on what the column *holds* rather
    # than on the text one dialect happens to store it as: SQLite hands back the
    # JSON as a string and PostgreSQL hands it back decoded, and neither of those
    # is what §74 is about.
    assert "NOTES_TOKEN" in str(row["secret_names"])
    assert "secret" not in str(row["configuration"]).lower()


async def test_disabling_keeps_the_configuration(session_factory) -> None:
    repository = SqlIntegrationRepository(session_factory)
    stored = notes()
    await repository.save(stored)

    await repository.save(stored.set_enabled(False))
    loaded = await repository.get(stored.id)

    assert loaded is not None
    assert not loaded.enabled
    assert not loaded.is_usable
    assert loaded.configuration == {"command": "python", "args": ["server.py"]}
    assert loaded.discovered == TOOLS, "nothing about its setup was forgotten"


async def test_a_failure_is_a_status_and_keeps_what_was_already_known(
    session_factory,
) -> None:
    repository = SqlIntegrationRepository(session_factory)
    stored = notes()
    await repository.save(stored)

    await repository.save(stored.failed(IntegrationStatus.CONNECTION_FAILED))
    loaded = await repository.get(stored.id)

    assert loaded is not None
    assert loaded.status is IntegrationStatus.CONNECTION_FAILED
    assert loaded.discovered == TOOLS


async def test_listing_and_removing(session_factory) -> None:
    repository = SqlIntegrationRepository(session_factory)
    first, second = notes(), Integration.create("issues")
    await repository.save(first)
    await repository.save(second)

    assert [item.name for item in await repository.list()] == ["issues", "notes"]
    assert await repository.delete(first.id) is True
    assert await repository.delete(uuid4()) is False
    assert [item.name for item in await repository.list()] == ["issues"]
