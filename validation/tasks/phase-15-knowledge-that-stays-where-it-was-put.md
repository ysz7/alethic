# Phase 15 validation - knowledge, and the boundary it stays inside

**Capability under test:** two things the platform could not do before. It can
now be *given* something to read - a document the user brought, which is not the
same as what the platform noticed about its own work - and it can keep contexts
apart, so that what was given in one is not available in another.

The second is the phase's Definition of Done, and it is deliberately a test the
platform passes by being *less* useful: the answer is in a document it holds,
one workspace away, and the right outcome is "I do not know". A boundary that
only holds when nothing is behind it is decoration.

## How it was run

Against locally served models, so the phase could be validated without a
provider key and without spending anything. `local-strong` is
`gemma4:31b-cloud`; the embeddings are `nomic-embed-text` on the same local
endpoint, which is also what the shipped catalog points at - what is embedded
here is the contents of the user's own documents, and there is no reason to send
them anywhere.

```bash
export PROMETHEUS_MODEL_CATALOG_PATH=infrastructure/llm/models.local.toml
export PROMETHEUS_DATA_DIR=... PROMETHEUS_APPROVAL_MODE=deny
uv run alembic upgrade head
uv run prometheus validate answer-from-a-document
uv run prometheus validate knowledge-stays-in-its-workspace
```

Both scenarios carry their own documents (`knowledge:` in the declaration), so
neither depends on anything already on this machine.

## The first run - failed, and the failure is the finding

`answer-from-a-document` asks how quickly express delivery arrives and what it
costs, with a delivery policy added to the workspace beforehand. It failed:

    [FAILED] PLANNING  0 step(s), $0.000000, 24s, 0 tool call(s)
      ok finished
      no output contains 'next working day'  (not in the answer)
      no output contains 'twelve'  (not in the answer)

> The delivery policy provided does not include details about express delivery
> arrival times or costs. No data on this topic is available in the current
> context.

Zero steps and zero tasks: the manager answered directly, and its answer was
that it had nothing to answer from. It was telling the truth. Retrieval was
wired into the *employee runtime's* context assembler, so a passage of a
document could only reach a run that had already been started - and this request
was correctly read as one that needed no work, so nothing was ever started.

Every unit test passed throughout. Nine hundred of them exercised retrieval
against a store; none of them asked whether the manager could see it, because
the manager and the runtime are tested separately and the seam between them is
exactly where this lived.

**Fixed:** `application/knowledge/workspace.py` is the manager's half of
retrieval, the shape `WorkspaceMemory` already had, read once per objective
beside it. The two are kept apart all the way into the prompt - a recollection
is a lead that may be stale, a passage of the user's own document is evidence
with a source attached - and `prompts/prometheus_intent/v4.md` says the second may
be answered from directly, naming the document.

## The second run - passed, 2026-09-08

    > answer-from-a-document
      [PASSED]  0 step(s), $0.000000, 15s, 0 tool call(s)
      ok output contains 'next working day'
      ok output contains 'twelve'

> Express delivery arrives the next working day and costs twelve euros.

Both facts exist only in the uploaded document. Still zero steps, which is the
right number: a question whose answer is in front of the platform is answered,
not decomposed into a plan to go and find what it already has.

## The Definition of Done - passed, 2026-09-08

`knowledge-stays-in-its-workspace` puts the same policy in `client-a` and asks
the same question in `personal`:

    > knowledge-stays-in-its-workspace
      [PASSED]  0 step(s), $0.000000, 11s, 0 tool call(s)
      ok output does not contain 'next working day'
      ok output does not contain 'twelve euros'

> I do not know.

And the control, run by hand immediately afterwards in `client-a`, where the
document actually is:

> Express delivery arrives the next working day and costs twelve euros.

Same platform, same question, same document, two workspaces - and the answer
differs. That is the phase.

## A defect the Definition of Done found in its own harness

The first passing run of `knowledge-stays-in-its-workspace` did not appear in
`prometheus validation-report` at all - it was listed as never attempted. The run
had been recorded in the workspace the *scenario* named, and the report reads
the workspace the machine is in, so a scenario about crossing a boundary filed
its own result on the other side of one.

Fixed by separating the two: the request is made in the scenario's workspace,
and the record of the run stays in the workspace the harness was called for. A
validation run is the platform's account of itself, like an audit line, and it
belongs where somebody will look for it.

## Where these runs are recorded

In a scratch data directory rather than in this machine's own store, so that
running the phase's scenarios did not add two workspaces and two documents to
somebody's real database. `validation/REPORT.md` is therefore unchanged by this
phase, and that is deliberate: it is a generated statement about one database,
and a hand-edited line in it would be the one thing it must never contain.

## What else the runs showed

**A question asked with "tell me you do not know rather than guessing" was once
escalated rather than answered.** In `client-a`, one run of that phrasing was
read as needing work, found no employee declaring the capability, and escalated
with "someone declared who can do this work". A re-run with a plainer question
answered correctly. This is the routing finding Phase 11 recorded and Phase 14
recorded again, not a knowledge one: the vocabulary an employee declares and the
requirement a plan states are matched too loosely, and the failure lands on the
user as an escalation.

**`answer-a-question` fails on this model today, before and after this phase.**
It asks for the capital of Australia and expects one step and no tools; the run
answers "Canberra" and takes two steps, having called `web.search`. Checked
against the previous intent prompt as well, to be sure the new one had not
caused it: same result. It is the same decomposition-when-none-is-needed
behaviour, and it belongs to the manager rather than to Phase 15.

## What is not established here

**The PostgreSQL backend has not been run.** There is no server on this machine.
The adapters, the dialect-aware upsert, the `tsvector` search and the migrations'
dialect branch are written and type-checked; the integration test
(`tests/integration/test_postgres_backend.py`) skips itself with the reason, the
way the local-provider test does. Until somebody runs it against a server, "the
platform works on PostgreSQL" is a claim this repository has not earned, and
`validation/REPORT.md` should not be read as saying otherwise.

**The move between stores has only been run between two SQLite files.** That run
copied everything - documents, chunks with their vectors, memory, workspaces -
verified it row by row, and left the source untouched until asked to erase it.
The same three steps against PostgreSQL are untested for the same reason.
