"""A JSON form in a prompt is a shape to fill, never an example to copy.

This is the first validation run's third finding, generalised. A cheap model
answered a verification prompt by returning the example it had been shown, so
the v2 verification prompts were rewritten to show an empty form. The same trap
was still in the intent prompt, and Phase 13 watched a local model read
"Hello" and answer with `{"format": "a file", "where": "somewhere named"}` -
the example's own values, invented as constraints on a greeting, which then
produced a plan, an employee and a file on disk.

So the rule is checked rather than remembered: the JSON block a prompt shows
must be empty. Strings blank, objects and arrays empty, numbers and booleans
left at whatever means "nothing said". A prompt that needs to explain a value
explains it in prose, where no model will mistake it for its answer.

Only the current version of each prompt is checked. An old version is a record
of what a past run was told, and rewriting it would destroy the only evidence
of why there was a next one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from application.prompts import PROMPTS_DIR, latest

#: The fenced JSON block a prompt shows as the shape of its answer.
FORM = re.compile(r"```json\n(.*?)```", re.DOTALL)

#: Prompts that still show a filled example, and have not been rewritten.
#:
#: Not an exemption - a queue, and since Phase 18 an empty one. All five were
#: rewritten under one validation run, which is what the queue was waiting for:
#: these forms are what weaker models lean on to produce a shape at all, and
#: swapping them for empty ones is a behaviour change that had to be measured
#: rather than assumed. Four of them lost their example and gained prose
#: describing the shape; `prometheus_reconciliation` lost the field instead, because
#: its one value was a `true` that meant "nothing to report" and is now read off
#: the list of contradictions being empty.
#:
#: The list may only shrink, and it has nothing left to shrink by. A new prompt
#: showing a filled form fails immediately, which is the point.
KNOWN_UNFIXED: frozenset[str] = frozenset()


def current_prompts() -> list[tuple[str, Path]]:
    return sorted(
        (directory.name, directory / f"{latest(directory.name)}.md")
        for directory in PROMPTS_DIR.iterdir()
        if directory.is_dir()
    )


def forms(text: str) -> list[dict]:
    """Every JSON form in a prompt, with the template's `{{` `}}` undoubled."""
    found = []
    for block in FORM.findall(text):
        try:
            found.append(json.loads(block.replace("{{", "{").replace("}}", "}")))
        except json.JSONDecodeError:
            # A block that is not one object is not a form the model fills in -
            # a fragment shown as illustration, or a list of examples in prose.
            continue
    return found


def filled(value: object) -> list[str]:
    """The parts of a form that carry a value somebody could copy."""
    if isinstance(value, dict):
        return [key for key, item in value.items() if item or filled(item)]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [] if value in ("", 0, False, None) else [str(value)]


@pytest.mark.parametrize("name,path", current_prompts(), ids=lambda item: str(item))
def test_the_form_a_prompt_shows_is_empty(name: str, path: Path) -> None:
    if not path.exists():
        pytest.skip(f"{name} has no versioned file")
    if name in KNOWN_UNFIXED:
        pytest.xfail(f"{name} still shows a filled form; see KNOWN_UNFIXED")
    offenders = {
        key: value
        for form in forms(path.read_text(encoding="utf-8"))
        for key, value in form.items()
        if filled(value)
    }
    assert not offenders, (
        f"{path.relative_to(PROMPTS_DIR.parent)} shows values a model can copy "
        f"instead of an empty form: {offenders}"
    )


def test_the_queue_of_unfixed_prompts_does_not_rot() -> None:
    """A name in the list that no longer exists is a rule nobody is enforcing."""
    existing = {name for name, _ in current_prompts()}
    assert existing >= KNOWN_UNFIXED, (
        f"KNOWN_UNFIXED names prompts that are gone: {KNOWN_UNFIXED - existing}"
    )
