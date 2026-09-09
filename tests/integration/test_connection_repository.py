"""Provider connections: an account, stored, with the key kept somewhere else.

Written against a real SQLite file, like every other repository test: the claim
is that what a person configured survives the process, and an in-memory database
would not exercise that.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.errors import ConfigurationError
from domain.providers.models import Connection
from infrastructure.llm.providers import KINDS, kind_named
from infrastructure.persistence.connection_repository import SqlConnectionRepository
from infrastructure.persistence.secret_repository import SqlSecretRepository
from infrastructure.secrets.encrypted import EncryptedCredentialStore
from infrastructure.secrets.encryption import Envelope


@pytest.fixture
def connections(session_factory: async_sessionmaker[AsyncSession]) -> SqlConnectionRepository:
    return SqlConnectionRepository(session_factory)


def a_connection(name: str = "openai-work", **extra) -> Connection:
    return Connection.create(name, "openai", secret_name=f"{name}_key", **extra)


async def test_two_keys_to_one_vendor_are_two_rows(
    connections: SqlConnectionRepository,
) -> None:
    """The reason a connection is not a provider: one person, two accounts."""
    await connections.save(a_connection("openai-work"))
    await connections.save(a_connection("openai-personal"))

    stored = await connections.list()
    assert [item.name for item in stored] == ["openai-personal", "openai-work"]
    assert {item.kind for item in stored} == {"openai"}
    assert [item.secret_name for item in stored] == ["openai-personal_key", "openai-work_key"]


async def test_a_connection_is_found_by_the_name_a_catalog_entry_would_use(
    connections: SqlConnectionRepository,
) -> None:
    await connections.save(a_connection("openai-work"))

    found = await connections.get_by_name("openai-work")
    assert found is not None and found.secret_name == "openai-work_key"
    assert await connections.get_by_name("openai-holiday") is None


async def test_a_connection_survives_being_written_twice(
    connections: SqlConnectionRepository,
) -> None:
    connection = a_connection()
    await connections.save(connection)
    await connections.save(connection.with_secret("rotated_key"))

    stored = await connections.list()
    assert len(stored) == 1
    assert stored[0].secret_name == "rotated_key"


async def test_removing_a_connection_leaves_nothing_behind(
    connections: SqlConnectionRepository,
) -> None:
    connection = a_connection()
    await connections.save(connection)

    assert await connections.delete(connection.id)
    assert await connections.list() == []
    assert not await connections.delete(uuid4())


async def test_the_row_names_the_credential_and_never_holds_it(
    session_factory: async_sessionmaker[AsyncSession],
    connections: SqlConnectionRepository,
) -> None:
    """The asymmetry the whole design rests on, asserted rather than described."""
    credentials = EncryptedCredentialStore(
        SqlSecretRepository(session_factory), Envelope(bytes(range(32)))
    )
    await credentials.store("openai-work_key", "sk-live-1234")
    await connections.save(a_connection())

    stored = (await connections.list())[0]
    assert "sk-live" not in str(stored)
    assert stored.secret_name == "openai-work_key"
    assert credentials.get(stored.secret_name).reveal() == "sk-live-1234"


async def test_a_local_runner_is_usable_with_no_credential_at_all() -> None:
    """The one kind that needs no account, and the reason `is_usable` exists."""
    local = kind_named("local")
    assert not local.needs_credential

    connection = Connection.create("ollama", local.name, needs_credential=False)
    assert connection.is_usable
    assert not Connection.create("openai-work", "openai").is_usable, "a key is missing"


def test_a_kind_nothing_implements_is_refused_rather_than_stored() -> None:
    """It would sit in the settings window looking configured and fail on the
    first call, which is the furthest possible point from the mistake."""
    with pytest.raises(ConfigurationError) as error:
        kind_named("some-startup")

    assert "openai" in str(error.value), "and says what this machine does have"
    assert {kind.name for kind in KINDS} >= {"openai", "anthropic", "local"}
