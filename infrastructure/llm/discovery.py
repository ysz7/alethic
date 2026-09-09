"""What a local model runner already has, so a person can pick from a list.

Adding a model by typing its name is how you get a settings page that accepts
`gemma3:27` and fails four hours later inside a task. The runner knows what it
has pulled; asking it is one request and turns a text field into a list.

Only the local kind is discovered, and that is not an oversight. A hosted
provider's catalogue is a moving list of hundreds behind an authenticated
endpoint whose shape differs per vendor, and what the platform needs to know
about a hosted model - what it can do, what it costs - is not in it. A local
runner's list is short, local, needs no key, and is exactly the set of things
that will actually run on this machine.

Failure is answered with an empty list and a log line, never an exception: a
runner that is not running is the ordinary state of a machine that uses hosted
models, and a settings page that fails to open because of it is a page that
punishes the common case.
"""

from __future__ import annotations

import httpx
import structlog

log = structlog.get_logger(__name__)

#: The runner's own API sits beside the OpenAI-compatible one it serves.
TAGS_PATH = "/api/tags"
DEFAULT_TIMEOUT_SECONDS = 5.0


def _root_of(base_url: str) -> str:
    """The runner's own address, from the chat endpoint the platform talks to.

    The catalog holds `http://host:11434/v1` because that is what the chat
    client needs; the tag listing is not under `/v1`. Trimming the suffix rather
    than storing a second address keeps one thing for a person to configure.
    """
    trimmed = base_url.rstrip("/")
    return trimmed[: -len("/v1")] if trimmed.endswith("/v1") else trimmed


async def installed_models(
    base_url: str, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
) -> tuple[str, ...]:
    """The names this runner has pulled, or nothing if it cannot be reached."""
    url = f"{_root_of(base_url)}{TAGS_PATH}"
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as error:
        log.info("models.not_discovered", url=url, error=str(error))
        return ()

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return ()
    names = [
        str(entry["name"]).strip()
        for entry in models
        if isinstance(entry, dict) and str(entry.get("name", "")).strip()
    ]
    log.info("models.discovered", url=url, count=len(names))
    return tuple(sorted(dict.fromkeys(names)))
