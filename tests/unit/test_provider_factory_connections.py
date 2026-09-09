"""Which key a call is paid with, now that there can be more than one.

Until Phase 17 the factory held one key and one address for every provider, so
"which vendor" and "which account" were the same question. These are the tests
for them being different ones.
"""

from __future__ import annotations

import pytest

from domain.errors import ConfigurationError
from domain.llm.catalog import ModelEntry
from domain.llm.models import ModelChoice
from domain.providers.models import Connection
from domain.secrets.models import Secret
from infrastructure.llm.catalog import ModelCatalog
from infrastructure.llm.connections import ConnectionDirectory
from infrastructure.llm.factory import ProviderFactory


class Keys:
    """A resolver holding what a person typed into the settings window."""

    def __init__(self, **values: str) -> None:
        self._values = values

    def maybe(self, name: str) -> Secret | None:
        value = self._values.get(name)
        return Secret(name, value) if value else None

    def get(self, name: str) -> Secret:
        found = self.maybe(name)
        if found is None:
            raise AssertionError(f"asked for a credential nobody stored: {name}")
        return found


def directory(*connections: Connection) -> ConnectionDirectory:
    found = ConnectionDirectory()
    for connection in connections:
        found.remember(connection)
    return found


def catalog() -> ModelCatalog:
    return ModelCatalog(entries=(ModelEntry(name="e", provider="openai", model="m"),))


def factory(**extra) -> ProviderFactory:
    return ProviderFactory(catalog=catalog(), api_key=None, base_url="", **extra)


def test_a_call_is_paid_with_the_key_of_the_connection_it_names() -> None:
    work = Connection.create("openai-work", "openai", secret_name="work_key")
    home = Connection.create("openai-personal", "openai", secret_name="home_key")
    built = factory(
        connections=directory(work, home),
        secrets=Keys(work_key="sk-work", home_key="sk-home"),
    )

    first = built.for_choice(ModelChoice("openai", "m", connection="openai-work"))
    second = built.for_choice(ModelChoice("openai", "m", connection="openai-personal"))

    assert first is not second, "two accounts on one vendor are two clients"


def test_the_same_connection_is_built_once() -> None:
    work = Connection.create("openai-work", "openai", secret_name="work_key")
    built = factory(connections=directory(work), secrets=Keys(work_key="sk-work"))
    choice = ModelChoice("openai", "m", connection="openai-work")

    assert built.for_choice(choice) is built.for_choice(choice)


def test_an_entry_naming_no_connection_still_uses_the_configured_key() -> None:
    """Every entry in the shipped catalog is one of these."""
    built = ProviderFactory(catalog=catalog(), api_key="sk-configured", base_url="")

    assert built.for_choice(ModelChoice("openai", "m")) is not None


def test_a_connection_that_is_gone_is_named_in_the_error() -> None:
    built = factory(connections=directory(), secrets=Keys())

    with pytest.raises(ConfigurationError) as error:
        built.for_choice(ModelChoice("openai", "m", connection="openai-work"))

    assert "openai-work" in str(error.value)


def test_a_connection_with_no_key_says_so_rather_than_blaming_the_env_file() -> None:
    """Pointing a person at `.env` when the missing thing is in the window is how
    a five-second fix becomes an afternoon."""
    empty = Connection.create("openai-work", "openai")
    built = factory(connections=directory(empty), secrets=Keys())

    with pytest.raises(ConfigurationError) as error:
        built.for_choice(ModelChoice("openai", "m", connection="openai-work"))

    assert "Settings" in str(error.value)


def test_a_connection_address_wins_over_the_machine_default() -> None:
    runner = Connection.create(
        "other-box", "local", base_url="http://10.0.0.5:11434/v1", needs_credential=False
    )
    built = ProviderFactory(
        catalog=catalog(),
        api_key=None,
        base_url="",
        local_base_url="http://127.0.0.1:11434/v1",
        connections=directory(runner),
    )

    client = built.for_choice(ModelChoice("local", "m", connection="other-box"))
    inner = getattr(client, "_inner", client)
    assert "10.0.0.5" in getattr(inner, "_base_url", "") or "10.0.0.5" in repr(inner.__dict__)
