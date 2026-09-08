"""The written answer Phase 11 exists to produce, computed rather than asserted.

Its Definition of Done is a sentence: *what does Alethic do reliably, what does
it do through gritted teeth, and what does it not do at all.* That sentence is
worth something only if it is derived from recorded runs, so this derives it -
and refuses to call anything reliable on the strength of a single success.

The thresholds are the argument, so they are stated here and nowhere else:

* **one pass is not reliability.** A capability that has worked once has worked
  once. It reads as SOMETIMES until it has done it again, which is the whole
  content of the word "reliably" (§11.5).
* **a skip is neither.** A scenario the machine cannot run says nothing about
  the platform, so it is excluded from every rate rather than counted as a
  failure. A completion rate that drops when the user switches off the desktop
  is not measuring the platform.
* **the failure that repeats is the one that matters.** A scenario's verdict
  carries the kind of failure that happened most often, because that is what
  the next piece of work has to be about (§11.6).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from statistics import median

from domain.validation.failures import FailureKind
from domain.validation.run import RunStatus, ValidationRun


class Verdict(StrEnum):
    #: Every attempt passed, and there was more than one attempt.
    RELIABLE = "RELIABLE"
    #: It has passed and it has failed - or it has passed exactly once, which
    #: is the same state of knowledge.
    SOMETIMES = "SOMETIMES"
    #: Attempted and never once finished to the standard written before it.
    NEVER = "NEVER"
    #: Never attempted here. Not a verdict about the platform.
    UNTRIED = "UNTRIED"
    #: This machine cannot run it, so nothing is known either way.
    UNAVAILABLE = "UNAVAILABLE"


#: How many passes it takes before a capability is described as reliable.
PASSES_FOR_RELIABLE = 2


@dataclass(frozen=True, slots=True)
class Reliability:
    """One scenario's history, reduced to the sentence a person needs."""

    scenario: str
    verdict: Verdict
    attempts: int = 0
    passes: int = 0
    skips: int = 0
    #: What went wrong most often across the failures. NONE where none did.
    common_failure: FailureKind = FailureKind.NONE
    median_steps: int = 0
    median_cost_usd: float = 0.0
    interventions: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passes / self.attempts if self.attempts else 0.0

    @property
    def in_regression_set(self) -> bool:
        """It worked here once, so it is expected to work here again (§11.5)."""
        return self.passes > 0


def reliability_of(scenario: str, runs: list[ValidationRun]) -> Reliability:
    """Reduce every recorded attempt at one scenario to a verdict."""
    mine = [run for run in runs if run.scenario == scenario]
    attempted = [run for run in mine if run.status is not RunStatus.SKIPPED]
    skips = len(mine) - len(attempted)
    passes = [run for run in attempted if run.passed]
    failures = [run for run in attempted if not run.passed]

    if not attempted:
        return Reliability(
            scenario=scenario,
            verdict=Verdict.UNAVAILABLE if skips else Verdict.UNTRIED,
            skips=skips,
        )

    if not passes:
        verdict = Verdict.NEVER
    elif not failures and len(passes) >= PASSES_FOR_RELIABLE:
        verdict = Verdict.RELIABLE
    else:
        verdict = Verdict.SOMETIMES

    kinds = Counter(
        run.failure for run in failures if run.failure is not FailureKind.NONE
    )
    return Reliability(
        scenario=scenario,
        verdict=verdict,
        attempts=len(attempted),
        passes=len(passes),
        skips=skips,
        common_failure=kinds.most_common(1)[0][0] if kinds else FailureKind.NONE,
        median_steps=int(median([run.metrics.steps for run in attempted])),
        median_cost_usd=median([run.metrics.cost_usd for run in attempted]),
        interventions=sum(run.metrics.interventions for run in attempted),
    )


@dataclass(frozen=True, slots=True)
class Report:
    """Every scenario's verdict, plus the totals the roadmap is argued from."""

    entries: tuple[Reliability, ...] = ()
    #: Failure kinds across every failed run, most frequent first. This is the
    #: list Phase 11 hands to whoever decides what Phase 12 does (§11.6).
    failures: tuple[tuple[FailureKind, int], ...] = ()
    total_runs: int = 0
    total_cost_usd: float = 0.0
    total_interventions: int = 0

    def of(self, verdict: Verdict) -> tuple[Reliability, ...]:
        return tuple(entry for entry in self.entries if entry.verdict is verdict)

    @property
    def completion_rate(self) -> float:
        """Passes over attempts, skips excluded (§11.4)."""
        attempts = sum(entry.attempts for entry in self.entries)
        passes = sum(entry.passes for entry in self.entries)
        return passes / attempts if attempts else 0.0

    @property
    def regression_set(self) -> tuple[str, ...]:
        return tuple(entry.scenario for entry in self.entries if entry.in_regression_set)


def build_report(scenarios: list[str], runs: list[ValidationRun]) -> Report:
    """The whole picture, from the declared scenarios and every recorded run.

    Scenarios drive the listing rather than the runs: one that has never been
    attempted has to appear as UNTRIED, because a report that only lists what
    was run cannot show what was avoided.
    """
    entries = tuple(reliability_of(name, runs) for name in scenarios)
    attempted = [run for run in runs if run.status is not RunStatus.SKIPPED]
    kinds = Counter(
        run.failure
        for run in attempted
        if not run.passed and run.failure is not FailureKind.NONE
    )
    return Report(
        entries=entries,
        failures=tuple(kinds.most_common()),
        total_runs=len(attempted),
        total_cost_usd=sum(run.metrics.cost_usd for run in attempted),
        total_interventions=sum(run.metrics.interventions for run in attempted),
    )
