"""A tool that keeps being refused stops being offered.

The first full validation run produced this in its plainest form: an analyst
whose policy forbids `code.run` asked for it fifteen times, was told no fifteen
times, and spent its entire step budget on the conversation. The refusal text
says "do not call this again". Text is a suggestion a model weighs, in exactly
the way §67 says a policy in a prompt is - so the refusal is made structural
instead. A tool refused often enough in one task is dropped from the tools the
model is shown, and there is nothing left to ask for.

Two distinctions carry the whole of this and both are deliberate.

**Refused is not failed.** A tool that ran and returned an error may work on the
next call - a page that timed out, a file that was not there yet - and dropping
it would take a working capability away over a transient fault. Refused means
the tool never ran: this employee may not have it, or a person said no. Nothing
about the next call changes that, so the count only ever includes those.

**Twice, not once.** A single refusal can be a mis-shaped call to a tool the
employee does have, and answering "no" to that once and then withdrawing it
would punish a typo. A second identical refusal is a decision to keep asking.

It is derived from the transcript rather than counted in the loop, so a run
resumed in another process withdraws exactly what the first one had.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from domain.tasks.plan import Observation

#: How many refusals of the same tool in one task are worth answering before it
#: is taken off the table.
REFUSAL_LIMIT = 2

#: The key an observation carries when the call never reached the tool.
REFUSED = "refused"


def refusal_counts(observations: Iterable[Observation]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for observation in observations:
        if observation.details.get(REFUSED):
            name = str(observation.details.get("tool", "")).strip()
            if name:
                counts[name] += 1
    return counts


def withheld(
    observations: Iterable[Observation], limit: int = REFUSAL_LIMIT
) -> frozenset[str]:
    """The tools this task may no longer be offered."""
    return frozenset(
        name for name, count in refusal_counts(observations).items() if count >= limit
    )
