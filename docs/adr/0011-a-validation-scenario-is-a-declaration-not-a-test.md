# ADR 0011 - A validation scenario is a declaration, and its verdict is stored

**Status:** accepted (Phase 11)

## Context

Ten phases were closed against `validation/tasks/`: a Markdown report per phase
saying what was asked, what came back, what broke, and what it cost. Those
reports are the most useful documents in the repository - three of the rules in
`CLAUDE.md` are defects those runs found before they were rules - and they have
two failings that only show up over time.

**A sentence in a report cannot be re-run.** Phase 4 sorted a folder in
September. Whether it still sorts a folder is unknown, and finding out means a
person reading the September report and retyping the request. §11.5 asks for the
opposite: a task Prometheus has done once should keep being done, and something has
to check.

**A verdict written by a person is an opinion about the platform.** The phase's
Definition of Done is a claim - what works reliably, what works sometimes, what
does not work at all - and every one of those words is about repetition. Nobody
remembers how many times the CSV scenario worked; they remember the last run.

The obvious answer, and the wrong one, is to make these tests. `tests/` has 900
of them, they run in seconds, they need no network and no key, and they are all
written against fakes on purpose. A scenario that ran against a fake model would
measure the fake. A scenario that ran against a real one in CI would make CI
cost money, need a key, and fail on the weather.

## Decision

### A scenario is a declaration in `validation/scenarios/`, discovered like everything else

The third registry of the same shape, after employees and workflows. A scenario
names what is asked, what the machine must have for the request to mean
anything, and what would count as done - and nothing else. Adding one is adding
a file; `tests/e2e/test_validation_harness.py` declares one in a temporary
directory and runs it, which is that claim as a test.

The prose reports stay where they are. `validation/tasks/` is what happened and
why, written for a person; `validation/scenarios/` is the request, written to be
made again. Merging them would produce either a report nobody can re-run or a
declaration nobody can read.

### The harness holds the platform's three doors and no fourth

`ValidationHarness` is given the manager, the task runner and the workflow
engine - the same three objects the CLI builds for `ask-prometheus`, `run-task` and
`run-workflow`. It cannot plan, choose an employee, call a tool or approve
anything. That restraint is the whole reason a run means something: whatever it
reports is what a person making the same request would have got. A fourth way to
run work would make the suite measure itself, exactly as a second employee
runtime would make the platform measure itself.

### Expectations are written before the run, and checked against the store

The discipline Prometheus applies to an objective, applied to the scenario. The
checks are a pure function over evidence gathered from what the platform already
writes down - the task rows, `tool_calls`, `audit_log`, the approvals table -
never from the summary the run returned. Phase 10 caught a workflow step that
said it had written the drafts and had called no tool at all; a harness that
believed the answer would have recorded that as a pass.

Two of the expectations are about what must *not* have happened. A run that
produced a good answer by sending something nobody approved has failed, and no
check on the output would notice.

### The failure is classified by type and counter, never by message text

`domain/validation/failures.py` names the categories the roadmap is written in
(§11.3): PLANNING, COMPUTER_USE, TOOL, MEMORY, MODEL, MISSING_CAPABILITY,
NEEDED_APPROVAL, BUDGET, EXPECTATION, ENVIRONMENT. It is not a second copy of
`application/orchestrator.py`: that one answers *should we retry* and has four
answers because four is what a retry decision needs. A run that failed because
nobody is declared for the work and one that failed because the model lost the
thread are both PERMANENT there and are entirely different pieces of work here.

### The verdict is stored, and one success is not reliability

`validation_runs` (migration 010), no foreign keys, for the reason `audit_log`
has none: the record outlives the tasks it describes, and the question it
answers is asked months later. `prometheus validation-report` computes the phase's
written answer from those rows, and a scenario that has passed exactly once
reads as SOMETIMES - which is the entire content of the word "reliably".

The regression set is derived rather than declared: a scenario that has passed
on this machine has earned its place in it, and `--regression` runs exactly
those. A hand-maintained list would drift, and would drift towards optimism.

## Consequences

* Closing a phase gains a mechanical half: the prose report still explains, and
  `prometheus validate` says whether the capability still works.
* The suite costs money and minutes, so it is a command and not something CI
  runs. `uv run pytest` remains free, offline and fast, and measures a different
  thing.
* A scenario the machine cannot run is SKIPPED with the reason, and skips are
  excluded from every rate. A completion rate that fell when the user switched
  off the desktop would be measuring configuration.
* Anything the harness cannot see is a gap in what the platform records, and
  finding those is part of the job. Counting how often a person had to answer
  needed `ApprovalRepository.for_task`, which did not exist: `list_pending`
  answers what still needs somebody, and by the time anyone asks about a
  finished run, nothing is pending.
* `prometheus validate` unattended is an honest reading of an unattended machine:
  anything needing approval is refused, and the report says NEEDED_APPROVAL
  rather than pretending the capability is missing.

## Alternatives considered

**Make them pytest tests marked `slow` and skipped by default.** They would
inherit the test suite's fixtures, its fakes and its assumptions, and the first
convenience anybody reached for would be a stubbed model. The separation is the
feature.

**Score the output with a model instead of declaring expectations.** A judge
model would let scenarios assert on prose, and would move the standard: the
judge is a model whose behaviour changes with the catalog, so a scenario's
meaning would change without the scenario changing. The expectations here are
deliberately mechanical - a file, a substring, a tool that did not run - and
where a scenario needs judgement, the platform's own verifier already gave one
and the harness records it.

**Keep the verdict in the Markdown report only.** It is where a person will read
it, and it is not where a comparison can be made. The report is now generated
from the rows, which is the same document with a source.

**Reconstruct the metrics from `tasks` and `tool_calls` at report time.** Those
tables know what ran; they do not know what the request was supposed to produce
or which capability was being asked for. It would mean re-deciding a judgement
months later with less evidence than was in front of it at the time.
