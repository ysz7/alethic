"""Verification is explicit. Success is never assumed.

A model reporting that it finished is evidence, not proof - it is the same model
that would report finishing if it had hallucinated the whole thing. So the
result is checked against the goal before a task is allowed to complete.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The floor under the model that is allowed to judge, on the catalog's own
#: quality ranking. Verification is a judgement, and the first full validation
#: run showed what happens when it is given to the cheapest entry in the
#: catalog: the verdict came back with `missing: ["which criterion is unmet,
#: and how"]` - the example out of its own prompt, copied word for word. A
#: check that cannot be trusted is worse than no check, because the run reads
#: as verified.
#:
#: Stated as a number rather than a model name so that changing models stays a
#: change to the catalog. It is deliberately low: this excludes the bottom of a
#: catalog, it does not demand the top.
MIN_JUDGEMENT_QUALITY = 0.5


@dataclass(frozen=True, slots=True)
class Verdict:
    passed: bool
    reason: str = ""
    #: What the verifier found missing. Fed back into a retry so the second
    #: attempt is better informed than the first, rather than merely repeated.
    missing: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def ok(cls, reason: str = "") -> Verdict:
        return cls(passed=True, reason=reason)

    @classmethod
    def rejected(cls, reason: str, *missing: str) -> Verdict:
        return cls(passed=False, reason=reason, missing=tuple(missing))
