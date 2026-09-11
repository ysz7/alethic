# Phase 16 validation - the report was measuring the harness

**What was under test:** not a new capability. Phase 16 exists because
`validation/REPORT.md` said three things did not work at all and named
`NEEDED_APPROVAL` eight times, and the roadmap is argued from that list. The
first question was whether those were defects of the platform or of the way the
suite runs it. The answer is: mostly the second, plus two defects the second was
hiding.

## What the recorded runs actually said

Every approval in the store - all 55 of them across 24 runs - was `REJECTED` by
`no-approver`. `prometheus validate` runs with nothing attached to stdin, so
`LocalApprovalService` correctly refused every action above the threshold. That
is the right behaviour for a machine nobody is watching, and it made three
scenarios impossible: the work each of them was written to measure begins with
writing a file.

Two things followed from it that nothing in the suite could say out loud.

**A scenario could not declare that somebody would have been there.** The
options were a machine-wide `PROMETHEUS_APPROVAL_MODE=allow`, which would also
switch off the brake in the scenario whose entire point is the brake, or the
unattended run, which is what happened. `use-a-connected-service` had already
worked around it in a comment: classify the integration's search as READ *so
that* the run does not spend itself on a question.

**The runs predate the code they were reported against.** They were recorded
between 07:42 and 08:46 on 2026-09-08; Phase 13, 14 and 15 were committed at
15:24, 18:28 and 20:46 the same day. The report the roadmap reads was measured
three phases back.

## Two defects in the verdict itself

Found by reading, confirmed by test, and both invisible to a suite whose runs
never got past the gate.

**A scenario declaring `must_succeed: false` could never pass.** `classify`
returned `NONE` only when `evidence.succeeded`, so the workflow that stops where
the sending would have been - correct behaviour, every declared check passing -
was recorded as FAILED. The declared expectations are the whole of the standard;
they now are.

**A refusal the scenario asked for was reported as the reason the run failed.**
`tools_denied` in an expectation is the author saying beforehand that this call
must not go through. Every such run reached the report under `NEEDED_APPROVAL`,
which is the one category that reads as "a person had to be there".

## What was built

* `Scenario.approve` - what the person at the keyboard would have said yes to,
  by tool name, declared before the run like every other expectation. Anything
  not named is refused. `DeclaredApprover` holds it for exactly one run;
  the harness opens and closes it and still cannot approve anything itself.
* `ApprovalRequest.tool` and migration 017. The stance is answered by tool name,
  never by reading the name back out of the rendered action line - `audit_log`
  has carried `tool` since Phase 10 and `approvals` had not.
* **The verifier is shown what the task did.** It is asked to fail a result that
  "claims something it does not show", and it was shown only the summary. The
  triage step of the inbox workflow listed a directory, read four files, and was
  rejected twice for producing "no evidence that the files were read" - which
  stopped the workflow before a single draft existed. It now gets the list of
  actions the platform already recorded. Phase 12 wrote this rule for accepting
  a task; the verifier was still judging on the report.
* `PRAGMA busy_timeout=5000`. WAL lets a reader and the writer work at once and
  does nothing about a second writer, which is what parallel employees and the
  scheduler are.

**One of those fixes was wrong twice before it was right**, and the way it was
wrong is worth keeping. The first version handed the verifier a truncated trace
of what each tool returned, and it started judging the answer against the trace:
a summary of two files of meeting notes was failed for naming an owner "not
present in the provided text", where the text it had seen was the first two
hundred characters of one read. The list now says what was called and whether it
returned, and nothing about what came back.

## What it changed

Before, on the same scenarios: 50% of attempts, three scenarios never passed.
After: 10/13 and 9/13 on two consecutive full runs, with all three of the
"does not work" scenarios passing at least once.

* `compute-from-a-csv` - PASSED. It reaches the arithmetic now, and writes
  2759.77.
* `triage-an-inbox` - PASSED. Drafts written, delivery refused, workflow stopped
  at `deliver` exactly as the phase intended.
* `remember-what-was-learned` - PASSED once, failed twice.
* `a-team-on-one-objective` - PASSED, which is Phase 17's scenario and not this
  phase's claim: one pass is not reliability, and the phase closes on a run of
  its own.

## What is still open

**Routing with an integration connected.** `use-a-connected-service` fails with
the analyst reaching for `code.run` to search notes rather than the tool the
integration supplied. The refusal is correct; the routing is what put it there.
Unchanged from what Phase 14 recorded, and still a job for the routing layer.

**Model variance is now the largest term.** Two consecutive full runs with the
same code disagreed on three scenarios. That is `gemma4:31b-cloud` and not the
platform, and it is the reason the report treats one pass as SOMETIMES.
