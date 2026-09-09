"""Encrypted credential storage. SQL does not leave this package.

What goes in and what comes out is ciphertext. Nothing here holds the master
key, decrypts anything, or knows what a credential is for - that is
`infrastructure.secrets.encrypted`, and keeping the split means a bug in the
storage layer cannot leak a value it never had.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.errors import StorageError, StorageNotInitializedError
from infrastructure.persistence.dialect import upsert
from infrastructure.persistence.models import SecretRow
from infrastructure.persistence.session import session_scope


@dataclass(frozen=True, slots=True)
class SealedSecret:
    """One credential as it is stored: a name and two opaque byte strings."""

    name: str
    ciphertext: bytes
    nonce: bytes


class SqlSecretRepository:
    """Reads and writes sealed credentials. Never sees a plaintext value."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[AsyncSession]:
        try:
            async with session_scope(self._session_factory) as session:
                yield session
        except OperationalError as error:
            message = str(error.orig)
            if "no such table" in message or "unable to open database file" in message:
                raise StorageNotInitializedError("The local database has no schema yet.") from error
            raise StorageError(message) from error

    async def save(self, secret: SealedSecret) -> None:
        now = datetime.now(UTC)
        values = {
            "name": secret.name,
            "ciphertext": secret.ciphertext,
            "nonce": secret.nonce,
            "updated_at": now,
        }
        async with self._session() as session:
            statement = upsert(session, SecretRow).values(**values, created_at=now)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[SecretRow.name],
                    set_={"ciphertext": secret.ciphertext, "nonce": secret.nonce,
                          "updated_at": now},
                )
            )

    async def list_all(self) -> list[SealedSecret]:
        async with self._session() as session:
            found = await session.execute(select(SecretRow).order_by(SecretRow.name))
            return [
                SealedSecret(name=row.name, ciphertext=row.ciphertext, nonce=row.nonce)
                for row in found.scalars()
            ]

    async def delete(self, name: str) -> bool:
        async with self._session() as session:
            result = await session.execute(delete(SecretRow).where(SecretRow.name == name))
            return bool(result.rowcount)
