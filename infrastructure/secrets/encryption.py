"""The master key, and the envelope every stored credential sits in.

Phase 17 puts credentials in the store rather than in a file beside it, because
the backend has to be deployable: a container that restarts with an empty
filesystem loses a file and keeps its database. That is only safe if what
reaches the database is unreadable without something the database does not have.

**The master key is that something, and it never goes near the store.**
`ALETHIC_MASTER_KEY` first - that is how a server is configured, and it is the
only sensible answer for a process with no persistent disk. Without it, a key is
generated once into a 0600 file beside the data, which is the desktop's answer.
The code is the same in both; only where the key came from differs.

Nothing here touches the operating system's own keychain. It would be the
stronger store on a laptop and it does not exist on the server this same backend
has to run on, and a platform whose security depends on which machine it was
started on has two behaviours to reason about instead of one.

AES-GCM, 256-bit, a fresh nonce per write, and the credential's own name as
associated data - so a ciphertext moved to another row stops decrypting rather
than quietly becoming a different credential's value.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import structlog
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from domain.errors import ConfigurationError, StorageError

log = structlog.get_logger(__name__)

#: Where a deployment says what the key is.
MASTER_KEY_ENV = "ALETHIC_MASTER_KEY"
#: Owner read/write, nothing for anybody else.
FILE_MODE = 0o600
DIRECTORY_MODE = 0o700
KEY_BITS = 256
NONCE_BYTES = 12


def resolve_master_key(data_dir: Path, environ: dict[str, str] | None = None) -> bytes:
    """The key, from the environment if it is there and from a file if it is not.

    Generating one on first use rather than refusing is deliberate: a desktop
    user who has never heard of a master key still gets encrypted credentials,
    and the alternative - refuse until configured - is the kind of ceremony that
    ends with people storing keys in plain text somewhere else.
    """
    environment = environ if environ is not None else dict(os.environ)
    raw = environment.get(MASTER_KEY_ENV, "").strip()
    if raw:
        try:
            key = base64.urlsafe_b64decode(raw)
        except (ValueError, TypeError) as error:
            raise ConfigurationError(
                f"{MASTER_KEY_ENV} is not valid base64. It must be a base64-encoded "
                f"{KEY_BITS // 8}-byte key."
            ) from error
        if len(key) != KEY_BITS // 8:
            raise ConfigurationError(
                f"{MASTER_KEY_ENV} must decode to {KEY_BITS // 8} bytes, got {len(key)}."
            )
        return key
    return _from_file(data_dir / "master.key")


def _from_file(path: Path) -> bytes:
    if path.exists():
        try:
            key = base64.urlsafe_b64decode(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as error:
            # Unreadable is not missing. Generating a new key here would leave
            # every stored credential undecryptable with no way back and no
            # message saying what happened.
            raise StorageError(f"the master key at {path} cannot be read") from error
        if len(key) != KEY_BITS // 8:
            raise StorageError(f"the master key at {path} is the wrong length.")
        return key

    key = AESGCM.generate_key(bit_length=KEY_BITS)
    path.parent.mkdir(parents=True, exist_ok=True, mode=DIRECTORY_MODE)
    temporary = path.with_suffix(".tmp")
    temporary.touch(mode=FILE_MODE)
    temporary.chmod(FILE_MODE)
    temporary.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="utf-8")
    temporary.replace(path)
    path.chmod(FILE_MODE)
    log.info("secrets.master_key_created", path=str(path))
    return key


class Envelope:
    """Encrypts and decrypts one value at a time. Holds the key and nothing else."""

    def __init__(self, key: bytes) -> None:
        self._cipher = AESGCM(key)

    def seal(self, name: str, value: str) -> tuple[bytes, bytes]:
        """The ciphertext and the nonce that produced it."""
        nonce = os.urandom(NONCE_BYTES)
        sealed = self._cipher.encrypt(nonce, value.encode("utf-8"), name.encode("utf-8"))
        return sealed, nonce

    def open(self, name: str, sealed: bytes, nonce: bytes) -> str:
        try:
            return self._cipher.decrypt(nonce, sealed, name.encode("utf-8")).decode("utf-8")
        except (InvalidTag, ValueError) as error:
            # The wrong key, a tampered row, or a value written under a key that
            # has since been replaced. All three mean the same thing to a
            # caller, and none of them may be answered with a guess.
            raise StorageError(
                f"the credential '{name}' cannot be decrypted with this master key"
            ) from error
