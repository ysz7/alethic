"""The phase's Definition of Done, rendered from what actually ran.

*"There is a written answer to the question: what does Prometheus do reliably, what
does it do through gritted teeth, and what does it not do at all."* The answer
has to be written, and it must not be written by hand - a hand-written answer is
an opinion about the platform, and the whole phase is an argument for measuring
instead of believing.

So this renders one Markdown document out of the recorded runs, and it says only
what the runs support. Where a scenario has never been tried it says so rather
than leaving it out; where a machine could not run one it says that too. A
report with a gap in it is useful, and a report that hides its gaps is not.

Markdown rather than a terminal table because the audience is a person reading
it next month, next to the prose reports in `validation/tasks/`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from domain.validation.failures import FailureKind
from domain.validation.reliability import Reliability, Report, Verdict

#: The order the sections appear in, and the sentence each one answers.
_SECTIONS: tuple[tuple[Verdict, str, str], ...] = (
    (
        Verdict.RELIABLE,
        "Works reliably",
        "Every recorded attempt met the criteria written before it, and there was "
        "more than one attempt.",
    ),
    (
        Verdict.SOMETIMES,
        "Works sometimes",
        "It has done this and it has failed to do this - or it has done it exactly "
        "once, which is the same state of knowledge.",
    ),
    (
        Verdict.NEVER,
        "Does not work",
        "Attempted here and never once finished to the standard set beforehand.",
    ),
    (
        Verdict.UNTRIED,
        "Not attempted",
        "Declared and never run here. Nothing is known either way.",
    ),
    (
        Verdict.UNAVAILABLE,
        "Not available on this machine",
        "Skipped: a capability the scenario needs is switched off here.",
    ),
)

#: What each failure kind means for whoever decides what to build next (§11.6).
_MEANS: dict[FailureKind, str] = {
    FailureKind.PLANNING: "the decomposition was wrong or absent",
    FailureKind.COMPUTER_USE: "the screen was misread, or an action did not land",
    FailureKind.TOOL: "a tool was reached for and did not do its job",
    FailureKind.MEMORY: "what should have been remembered was not there",
    FailureKind.MODEL: "the model lost the thread, or the provider did",
    FailureKind.MISSING_CAPABILITY: "nothing declared here can do this - roadmap, not bug",
    FailureKind.NEEDED_APPROVAL: "the brake held and nobody was there to answer",
    FailureKind.BUDGET: "steps, money or time ran out",
    FailureKind.EXPECTATION: "it finished, and produced something other than what was asked",
    FailureKind.ENVIRONMENT: "this machine is set up wrong",
    FailureKind.UNKNOWN: "not yet classified - the taxonomy has a gap",
}


def render(report: Report, *, now: datetime | None = None) -> str:
    """The whole document, as Markdown."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    lines: list[str] = [
        "# What Prometheus can actually do",
        "",
        f"Generated from {report.total_runs} recorded run(s) on {stamp} by "
        "`prometheus validation-report`. Every line below is a verdict on scenarios "
        "declared in `validation/scenarios/`, measured against criteria written "
        "before each run.",
        "",
        f"- Completed to the stated standard: **{report.completion_rate:.0%}** of attempts",
        f"- Spent across every attempt: **${report.total_cost_usd:.4f}**",
        f"- Times a person had to answer something: **{report.total_interventions}**",
        "",
    ]

    for verdict, title, explanation in _SECTIONS:
        entries = report.of(verdict)
        if not entries:
            continue
        lines += [f"## {title}", "", explanation, ""]
        lines += [_line(entry) for entry in entries]
        lines.append("")

    if report.failures:
        lines += [
            "## What went wrong, by kind",
            "",
            "The list the roadmap is argued from: the categories at the top are "
            "where the next piece of work is, whatever was planned instead.",
            "",
        ]
        for kind, count in report.failures:
            lines.append(f"- **{kind.value}** x{count} - {_MEANS.get(kind, '')}")
        lines.append("")

    regression = report.regression_set
    lines += [
        "## The regression set",
        "",
        "Scenarios that have passed here at least once. Each is expected to keep "
        "passing; `prometheus validate --regression` runs exactly these.",
        "",
    ]
    lines += [f"- `{name}`" for name in regression] or ["Nothing has passed here yet."]
    lines.append("")
    return "\n".join(lines)


def _line(entry: Reliability) -> str:
    if entry.verdict in (Verdict.UNTRIED, Verdict.UNAVAILABLE):
        return f"- `{entry.scenario}`"
    detail = f"{entry.passes}/{entry.attempts} passed"
    if entry.median_steps:
        detail += f", median {entry.median_steps} step(s)"
    if entry.median_cost_usd:
        detail += f", median ${entry.median_cost_usd:.4f}"
    if entry.common_failure is not FailureKind.NONE:
        detail += f", usually {entry.common_failure.value}"
    return f"- `{entry.scenario}` - {detail}"
