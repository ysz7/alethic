# ADR 0017 - Storage is a setting, and moving is copy, verify, erase

**Status:** accepted (Phase 15)

## Context

§3 chose SQLite natively and without hedging: one file instead of a daemon and a
container, so there is no database installation between `clone` and `run`. §4
then deferred PostgreSQL behind three triggers and said the question would not
be reopened until one of them fired.

Trigger 1 has now fired. It reads: *FTS5 stopped coping with recall - semantic
search is needed rather than lexical - therefore pgvector.* Phase 15 is where
that happens: a lexical index finds "shipping" by the word "shipping" and not by
the word "delivery", which was tolerable for memory a sentence long and is not
for a forty-page document.

But the trigger's conclusion does not follow on its own, and the platform has a
second constraint that did not exist when §4 was written: since Phase 13 there
is a desktop application, and an application that cannot start without a
database server is a different product from the one that opens and works.

## Decision

### The trigger fired; the conclusion is refused, with a reason

Semantic search is needed. PostgreSQL is not needed *for it*. One person's
knowledge is thousands of chunks, not millions; a cosine over a matrix held in
memory answers in milliseconds at that size, with no extension and no daemon.
pgvector wins where the index does not fit in memory and approximate search
starts to pay - which is a real place and not this one yet.

So the local implementation is the default, and §4's rule is honoured rather
than broken: the trigger is what allowed the question to be asked, and the
answer is written down here so the next reader does not re-derive it.

### PostgreSQL is a second adapter, not a replacement

Behind the same protocols. `TaskRepository`, `Memory`, `AuditLog`,
`KnowledgeStore` and the rest are `Protocol`s in `domain/`, and no query leaves
`infrastructure/persistence/` - which is exactly the debt §4 said was being paid
in advance. Adding a backend is new adapters and new migrations; `domain/`,
`application/`, `employees/` and the prompts do not change.

Supabase is not a third backend. It is the same adapter with a different
connection string, and treating it as one would mean maintaining two
implementations of one dialect.

**The default stays SQLite.** `clone && run` keeps working, the packaged window
keeps starting, and the person who wants a server opts into one.

### One database for everything

Not "a memory backend". Tasks, objectives, plans, memory, knowledge, audit,
integrations and schedules live in one store. Splitting them - memory on
PostgreSQL, tasks on SQLite - would mean two stores that can disagree about what
happened, and two migrations instead of one.

### Moving is copy, verify, then a separately confirmed erase

"After moving to B the data is not left on A" is the right goal and has exactly
one safe order: create the schema on B, copy, **verify row by row**, and only
then erase A.

Erasing the source is irreversible, and irreversible actions in this platform
wait for a person (ADR 0004). So it is a distinct, confirmed step that says what
is about to be destroyed - not the tail of a command that also did the copying.
The state in between, where the data is on B and still on A, is not a defect: it
is the point at which the move can still be abandoned.

Verification compares counts and rows rather than trusting that the copy
returned without raising - the same rule as the validation harness, which checks
the store rather than the summary the run produced (ADR 0011).

Two things do not move. The credential file is a file on this machine and stays
one (§74). The full-text index is rebuilt rather than copied, because FTS5 and
`tsvector` are different things - which is also why it is generated from the
schema on both sides rather than migrated as data.

### pgvector is not part of this, and the reason is written down

The phase plan lists "PostgreSQL + pgvector"; what shipped is PostgreSQL, and
vectors are `bytea` on both backends with the cosine computed in memory. That is
the same argument as above, applied one level down: at one person's scale the
comparison costs milliseconds, and an extension the user has to install is
exactly the kind of requirement §3 spent effort avoiding.

It also keeps the two backends identical where it matters - a chunk written on
SQLite and copied to PostgreSQL is the same row, which is what makes the move a
copy rather than a re-index.

The trigger for revisiting is the same shape as §4's: **when the vectors for one
workspace no longer fit comfortably in memory, or a retrieval spends more time
on the cosine than on the model call.** Then pgvector is a column type and an
index on the PostgreSQL adapter, and the local one keeps what it has.

### A chunk records the model that embedded it

Restated here because a move is where it bites: vectors copied to another store
are only meaningful if whatever queries them embeds with the same model. Name
and dimension travel with the row, a mismatch means re-indexing, and nobody has
to guess.

## Consequences

* The desktop application keeps being installable without a server, which is
  what §3 bought and what a database requirement would silently spend.
* There are two persistence implementations to keep honest. The integration
  tests already run against a real file rather than an in-memory database
  because restart survival is the point; the PostgreSQL ones need a server, so
  they are skipped where there is none - the same rule
  `tests/integration/test_local_provider.py` already follows.
* Thirteen migrations are written natively for SQLite and several repositories
  use `dialects.sqlite.insert` for upsert. A second backend means a second set,
  and that cost is visible here rather than discovered halfway through.

## Alternatives considered

**Move to PostgreSQL outright.** Simpler to maintain - one backend - and it ends
the local-first product: `clone && run` becomes `clone && install && run`, and
the window needs a server behind it. That is a positioning decision, not a
storage one, and it should be made deliberately rather than as a side effect of
wanting better search.

**Keep SQLite only and do without semantic search.** It is what §4 said until
the trigger fired. Retrieval over documents is the capability this phase exists
for, and lexical retrieval over long documents answers beside the question.

**Ship an embedded PostgreSQL inside the application.** It exists, and it would
give pgvector without a daemon the user manages. It also adds a platform-specific
binary to every build for a capability the local implementation already provides
at this size. Worth revisiting if the local store stops coping - which is the
same shape of trigger as §4's, and should be written down as one when it is.

**Copy without erasing.** Leaves the user's data in two places with no statement
about which is authoritative, and the second one is the one nobody remembers to
protect.

## Confirmed in Phase 19, with three corrections to this decision's own terms

Everything above was written before a server existed on this machine. Phase 19
ran it - migrations, the whole test suite, a real move in both directions, and
the validation set - and the decision holds: no failure was classified as
storage, and nothing above `infrastructure/` had to change. The record is
`validation/tasks/phase-19-postgresql-confirmed-on-a-real-server.md`. Three
things in this document turned out to be understated.

**"What actually differs is small" needed a third entry, and it is time.** The
domain works in aware UTC and the columns are naive; SQLite forgave that on the
write side for eighteen phases and PostgreSQL refuses it outright. The
conversion belongs on the column type (`dialect.UtcTimestamp`), where it is
stated once, rather than in the eleven repositories that had each written half
of it.

**A copy is not finished when the rows have arrived.** Four tables number their
own rows, and on PostgreSQL the number comes from a sequence the copy never
touches. A store that verified row for row could not then take one more row.
Advancing the sequences is part of `copy`, not a step after it: a move that
leaves the destination unwritable is not a move, and the person watching it has
no way to know.

**"Both return the same thing to the domain" was not true of the words.** The
two indexes tokenised differently and combined a query's words differently, so
what a person could find depended on which backend they had chosen - the drift
ADR 0016's normalisation was supposed to make impossible, sitting one level
below where that normalisation happens. The query expression and the index
expression are now one constant per index, and the words are joined the same way
on both.
