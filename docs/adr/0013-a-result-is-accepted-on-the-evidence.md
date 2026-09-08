# ADR 0013 - A result is accepted on the evidence, not on the report

**Status:** accepted (Phase 12)

## Context

§88 asks Alethic to validate an employee's output before accepting it, and notes
that an employee verifying its own work is necessary but not sufficient. Until
Phase 12 the platform had the necessary half twice - the employee runtime
verifies each task against its goal, and the manager verifies the objective
against its acceptance criteria - and both of them are model calls reading
prose.

The first full validation run showed what that misses. An employee reported
success having had every one of its tool calls refused: nothing it tried to do
happened, and the closing message was a confident summary of the work it would
have done. Both verifiers read that message. Both are capable of noticing; a
model asked whether an answer is supported will sometimes say no. Sometimes is
not a property worth building a gate out of.

## Decision

**The manager's acceptance check is a fact about the record, not an opinion
about the text.** `domain/workforce/acceptance.py` reads the observations the
task left behind and answers one question: did anything this task attempted
actually reach the world?

A task that reached for tools and had every one of them refused or fail is not
accepted, whatever its summary says. It costs nothing, it runs on every task,
and it cannot be talked out of it.

Two deliberate omissions.

**It does not fail a task that used no tools.** Judgement is real work -
deciding, comparing, writing an answer from what was passed down - and
demanding evidence of action from work whose product is a sentence would reject
the tasks this platform is best at.

**It does not judge quality.** Whether the answer is good is the verifier's
question, asked against the objective's own criteria. This one answers only
whether anything happened, which is precisely the question no amount of reading
the answer can settle.

The two halves of the answer are kept apart, because the recovery differs: work
blocked by permission may reach somebody else (reassign), work that simply did
not happen needs a different plan (replan). That is the same distinction
`supervisor.classify` already makes for failures, extended to a task that
"succeeded".

The task row is not rewritten. It keeps saying what the runtime concluded, and
the manager's refusal sits beside it on the outcome - the disagreement between
the two is the interesting part, and overwriting one with the other would lose
it.

## Alternatives rejected

**A second model call to judge each result.** More expensive per task than the
whole check, and it fails exactly where the first one did: it reads the same
confident summary.

**Make the runtime fail the task instead.** The runtime is the witness under
question. A run that concludes it succeeded is not the right place to record
that it did not, and moving the check there would mean the manager accepts
whatever the runtime says - which is where this started.
