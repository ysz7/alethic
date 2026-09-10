# Phase 19 validation - PostgreSQL, on a server that exists

**What was under test:** the claim that storage is a setting. The second backend
was written in Phase 15 and had never run: this machine had no server, the one
integration test that wanted one skipped itself with a reason, and everything
anybody knew about PostgreSQL here came from reading the code and from a suite
that ran against SQLite. ADR 0017 says the two are one set of adapters rather
than two. Until this phase that was a design intention.

**The server:** PostgreSQL 18.6, a cluster of its own on port 55432, started
from the binaries already installed on this machine and pointed at a scratch
data directory. Separate deliberately - the platform's own database and the
user's existing cluster took no part in any of this. Models: `gemma4:31b-cloud`
for the work that decides things, `lfm2:24b` and `lfm2.5:8b` for the small
structured jobs. No key, no spend.

**Result:** six defects, every one of them invisible to the 1087 tests that
passed before the phase started, and five of the six impossible to see without a
server. Two of them made the second backend unusable outright - one before the
schema existed, one after a verified move.

## What the run found

### The migrations did not run at all

`alembic upgrade head` failed on the fourth migration:

```
column "success" is of type boolean but default expression is of type integer
```

Two migrations wrote a boolean default as `sa.text("1")` and six wrote it as
`sa.true()`. SQLite accepts either, because it has no boolean type; PostgreSQL
accepts only the second. So the first sentence of the phase - "run the
migrations there" - could not be carried out, and nothing in the repository
said so.

**Fixed** by making the two agree with the six. Not by writing a
dialect-agnostic subset of SQL: the conventions here say migrations are written
natively, and 007 and 016 already branch where FTS5 and `tsvector` genuinely
differ. A boolean default is not that kind of difference; it was a slip that
one backend forgave.

### The platform could not write a timestamp

Every domain value carries an aware UTC moment (`datetime.now(UTC)`) and every
column is naive, which is what migration 001 gave both backends. SQLite stores a
string and hands one back, so the conversion existed on the read side only - a
`_aware` helper that eleven repositories each kept a copy of - and the write side
worked by accident for eighteen phases. PostgreSQL refuses an aware value for
`TIMESTAMP WITHOUT TIME ZONE`, so *every* insert failed.

**Fixed** on the column type, once: `dialect.UtcTimestamp` converts on the way
in and attaches UTC on the way out, and `Base.type_annotation_map` applies it to
all forty-three `Mapped[datetime]` columns. The alternative was widening every
timestamp in the schema to `timestamptz` in order to store what is already
always UTC, and the alternative *actually* in front of me was adding the missing
half of the conversion to eleven repositories and to the twelfth somebody writes
next year.

### The harness was holding up the thing it was meant to check

`create_all` attaches the text index to the metadata with
`execute_if(dialect="sqlite")`, so a PostgreSQL schema built from the metadata
had no text index at all - and the one test that searched there created the two
GIN indexes itself, in its own fixture. It passed. What it proved was that
searching works on a schema the test had repaired.

This is Phase 16's lesson in a different place, and it is worth stating plainly
because the comment directly above the offending loop already contains the
argument against it: *"a database built by `create_all` has to be searchable the
same way the migrated one is, or the tests exercise a different backend than the
product ships."*

**Fixed** by listening to that comment: the PostgreSQL statements are attached
to `after_create` too, and the fixture that used to compensate no longer does.

### The two indexes were answering different questions

With the suite finally running on the second dialect, five memory tests failed,
and they were not about the plumbing.

`plainto_tsquery` joins the words a person typed with `and`. The SQLite branch
asks FTS5 for `"where" OR "is" OR "the" OR "report"`. So *"where is the
report"* found the note on SQLite and found nothing on PostgreSQL, because no
note contains every word of the question. **Fixed** with `to_tsquery` and `|`.

Then: PostgreSQL's default parser knows a file name when it sees one and keeps
`reports/q2.md` as a single token, while FTS5's `unicode61` splits it into
`reports`, `q2`, `md`. A note saying where the report is was therefore findable
by searching for `q2` on one backend and not on the other. **Fixed** by indexing
`regexp_replace(content, '\W+', ' ', 'g')` - `unicode61`'s rule stated in the
other dialect's terms - in migration 021, over both `memory_items` and `chunks`.
The expression lives beside the SQLite version in `memory_fts` and
`knowledge_fts`, and the adapter's query is built from the same constant,
because an expression index that does not match the query exactly is an index
the planner silently declines to use.

Both are the drift ADR 0016 exists to prevent, and both had been in the
repository since Phase 15. What a person can remember was a function of which
backend they had chosen.

### The worst one: a store that arrived verified and could not be written to

The move itself went cleanly the first time it was tried on real data - 195
rows copied, then compared row by row, counts and contents, then the source
erased as a separate confirmed act. The store read back completely: workspaces,
documents, the schedule, the audit lines, and memory searchable by words.

Then the validation set was run against it, and all thirteen scenarios failed
within a second of starting:

```
duplicate key value violates unique constraint "task_events_pkey"
DETAIL:  Key (id)=(2) already exists.
```

Four tables number their own rows, and on PostgreSQL the number comes from a
sequence rather than from the column. A copy inserts the ids it was given and
says nothing to the sequence, so every one of the four still sat at 1: the first
task event written after the move asked for an id that had arrived from SQLite
an hour earlier, and so did the next twenty-three.

A move that verifies row for row and leaves the store unable to take one more
row is not a move. **Fixed** inside `transfer.copy` - not as a tidy-up after it -
by advancing each destination sequence past what arrived (`dialect.advance_identity`).
Nothing on SQLite, which takes the next id from the highest one present and so
has already been told everything by the rows themselves.

No test could have caught this, and the reason is worth keeping: a test builds an
empty schema and inserts into it, which is the one case where the sequence is
already right. It is now a test in `test_postgres_backend.py`, which runs only
when a server is configured - the argument for that file existing at all.

### Two numbers about an irreversible act that disagreed

`storage-migrate --erase` said *"About to erase 195 row(s)"* and then *"Erased
193 row(s)."* Both were reporting a complete erase. A retry hangs off the task
that failed, so deleting the parent tasks took two child tasks with it by
cascade, and `rowcount` counts only the rows a statement removed itself. **Fixed**
by counting before deleting: twenty-five cheap counts is the right price for the
one number that is true, in the message a person reads before authorising
something that cannot be undone.

## The validation set on the second dialect

The whole set, run against the store that had just been moved onto PostgreSQL,
and then run again on a fresh SQLite store on the same machine with the same
models - because a single pass of a noisy process says nothing on its own, and
what is being asked is whether the *dialect* changes anything.

| scenario | PostgreSQL | SQLite |
|---|---|---|
| `research-from-the-web` | PASSED | PASSED |
| `sort-a-folder` | FAILED MODEL | FAILED MODEL |
| `answer-a-question` | FAILED MODEL | PASSED |
| `state-a-goal` | PASSED | FAILED MODEL |
| `compute-from-a-csv` | FAILED MODEL | FAILED MODEL |
| `remember-what-was-learned` | FAILED EXPECTATION | FAILED TOOL |
| `nothing-sent-without-consent` | PASSED | PASSED |
| `triage-an-inbox` | PASSED | FAILED MODEL |
| `a-team-on-one-objective` | FAILED NEEDED_APPROVAL | FAILED NEEDED_APPROVAL |
| `use-a-connected-service` | FAILED MODEL | FAILED MODEL |
| `answer-from-a-document` | FAILED NEEDED_APPROVAL | FAILED NEEDED_APPROVAL |
| `knowledge-stays-in-its-workspace` | FAILED PLANNING | FAILED PLANNING |
| `operate-a-screen` | not available here | not available here |

4 of 12 attempted on PostgreSQL, 3 of 12 on SQLite, and **not one failure
classified as storage**. Nine of the twelve landed on the same verdict with the
same failure kind on both. The three that differ - `answer-a-question`,
`state-a-goal`, `triage-an-inbox` - differ in both directions and each is a
MODEL failure on the side that lost, which is the variance Phase 18 already
recorded for these models on these scenarios and the reason the report in
`validation/REPORT.md` speaks in ratios rather than in verdicts.

Two things are worth reading off the table rather than off the summary. The pass
rate is low against the 58% in `REPORT.md` because these are single attempts on
a fresh store with no memory of anything - `REPORT.md` is 106 runs, and it has
deliberately not been regenerated from this phase's twelve. And
`answer-from-a-document` failed on both while its output contained *"next
working day"* and *"twelve"*: the document was retrieved out of PostgreSQL and
reached the answer, and what failed after that was the manager writing it to a
file nobody asked for. Phase 19's question about that scenario is answered;
Phase 20's is not.

## What this cost above the storage layer

Nothing, which was the claim. `domain/`, `application/`, `employees/`,
`prompts/` and `desktop/` are untouched. Inside `infrastructure/`, the two
adapters that already held the dialect branch gained the same branch's
correction (`memory/sql.py`, `knowledge/store.py`) and the rest is
`persistence/`.

One change is outside all of it and is not about dialects at all:
`alethic validate` computed its closing line as *total minus failures*, so the
scenario this machine cannot attempt was counted as a scenario that worked, and
the run above reported "5/13 passed" with four passes. It is the one number a
person takes away from the command, so it is now counted rather than inferred.

`tests/conftest.py` is where the phase's real leverage turned out to be:
`ALETHIC_TEST_POSTGRES_URL` now moves the *whole* suite onto the second dialect
instead of enabling three hand-written tests. Thirteen repositories cannot be
covered by three tests, and the three that were there agreed with everything
while two of the defects above sat in the schema. 1089 tests pass on
PostgreSQL and 1087 on SQLite - the difference is the two tests that need a
server and skip where there is none.

## What stays open

**pgvector, deliberately.** Vectors are bytes on both backends, compared in
memory. ADR 0017 records the trigger for revisiting that, and one person's
scale is not it.

**The move was verified in both directions but only at one scale.** 195 rows,
which fits in a single batch of 500. The batching, the resumption of an
interrupted copy and the behaviour of `verify` over a table that does not fit in
memory are still held up by unit tests and by reading the code.

**No concurrency was tested.** Two writers is the second of the two open
triggers for making PostgreSQL the primary store, and nothing here exercised it:
one process, one connection pool, one machine.

**The scheduler and the desktop window never saw the second backend.** Both talk
to the same repositories through the same contracts, and neither was started
against PostgreSQL in this phase.
