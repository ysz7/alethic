"""Prompt templates, loaded from files and versioned there.

Prompts are content, not code: they change far more often than the loop around
them, and a diff on a `.md` file is readable in a way that a diff on an embedded
triple-quoted string is not.

It sits at the top of `application/` rather than inside the employee runtime
because the manager writes prompts too, and Prometheus reaching into the runtime's
package for a file loader would suggest a dependency that does not exist.

**Versioning is the directory, not a field** (§121). `prompts/<name>/v2.md`
sitting next to `v1.md` is the whole mechanism: the old text stays readable, the
change is a diff between two files rather than a rewrite of one, and a caller
that wants the text a past run used asks for it by name. `latest` is the
default because a caller that does not care should get the current wording, and
a caller that does care should have to say which one.

**A digest, because reproducibility needs one.** "v1" says which file; the hash
says whether that file is still what it was when a run used it. Editing a prompt
in place without bumping the version is the thing that silently makes two runs
incomparable, and this is what makes it visible.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from domain.errors import ConfigurationError

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

#: What a version file is called. Ordered numerically, so v10 follows v9.
VERSION_PATTERN = re.compile(r"^v(\d+)$")

LATEST = "latest"


@dataclass(frozen=True, slots=True)
class PromptInfo:
    """One prompt as an asset: what versions exist and what the current one is."""

    name: str
    versions: tuple[str, ...]
    digest: str

    @property
    def latest(self) -> str:
        return self.versions[-1]


def _version_number(version: str) -> int:
    match = VERSION_PATTERN.match(version)
    return int(match.group(1)) if match else -1


@lru_cache(maxsize=32)
def versions(name: str) -> tuple[str, ...]:
    """Every version of one prompt, oldest first."""
    directory = PROMPTS_DIR / name
    if not directory.is_dir():
        return ()
    found = [path.stem for path in directory.glob("v*.md") if VERSION_PATTERN.match(path.stem)]
    return tuple(sorted(found, key=_version_number))


def latest(name: str) -> str:
    found = versions(name)
    if not found:
        raise ConfigurationError(f"No prompt named '{name}' under {PROMPTS_DIR}")
    return found[-1]


@lru_cache(maxsize=32)
def load(name: str, version: str = LATEST) -> str:
    resolved = latest(name) if version == LATEST else version
    path = PROMPTS_DIR / name / f"{resolved}.md"
    if not path.exists():
        raise ConfigurationError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def digest(name: str, version: str = LATEST) -> str:
    """A short hash of the text actually loaded. Twelve hex characters is
    plenty to notice an edit and short enough to print next to a version."""
    return hashlib.sha256(load(name, version).encode()).hexdigest()[:12]


def catalog() -> list[PromptInfo]:
    """Every prompt that ships here, for `prometheus prompts` and for a test that
    checks the ones the code asks for are the ones on disk."""
    if not PROMPTS_DIR.is_dir():
        return []
    found = []
    for directory in sorted(PROMPTS_DIR.iterdir()):
        if not directory.is_dir():
            continue
        available = versions(directory.name)
        if available:
            found.append(
                PromptInfo(
                    name=directory.name,
                    versions=available,
                    digest=digest(directory.name),
                )
            )
    return found


def render(name: str, version: str = LATEST, **values: object) -> str:
    template = load(name, version)
    try:
        return template.format(**values)
    except KeyError as error:
        raise ConfigurationError(
            f"Prompt {name}/{version} references {error} but it was not supplied"
        ) from error
