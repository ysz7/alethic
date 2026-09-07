# ADR 0009 - Memory is reached only through `recall`, and a scope is a boundary

**Status:** accepted (Phase 9)

## Context

Phase 9 gives the platform a memory: what a task learned, what a plan produced,
how the user wants work done here. The store that makes this fast on SQLite is
FTS5 - a virtual table with triggers keeping it in step - and it is the only
SQLite-specific thing in the whole schema. Everything else in `infrastructure/`
is written natively for SQLite but says nothing that could not be said to
another database; a full-text index is not.

There is also a second question that arrives with memory and not before it.
Tasks and approvals belong to whoever asked for them; a *memory* is about
somebody. An employee's notes on how it works, the user's stated preferences and
one plan's intermediate results are three different audiences, and the cheap
answer - one table, a `scope` column, and callers that pass the right filter -
makes every caller responsible for a rule that only has to be got wrong once.

## Decision

### One contract, and no search around it

`domain.memory.protocols.Memory` has two methods: `remember` and `recall`. Every
search goes through `recall`. Nothing in `domain/`, `application/`, `app/`,
`employees/` or `prompts/` names `memory_items`, `MATCH`, `fts5` or `bm25`, and
`tests/unit/test_memory_access_rule.py` fails the build if one appears.

Forgetting is a second contract, `MemoryMaintenance`, implemented by the same
adapter. Reading and deleting happen over the same rows, so one object serves
both; they are separate interfaces so that holding `recall` does not hand a
caller the power to delete.

### The policy is the domain's; the index is the backend's

The store answers *which items mention this*. What is worth reading now is
decided in `domain/memory/ranking.py`: relevance x importance x decay, with a
half-life and a time to live per kind. A backend's own rank is normalised to a
fraction of its best hit before the domain sees it, so the policy means the same
thing on FTS5 as it will on a vector store.

Ranking by the index alone would return the best textual match to "the report",
which is every report ever written. Ranking without the index would mean reading
everything to answer anything.

### A scope is enforced where the rows are

`domain/memory/access.py` states, once, who may read what: the workspace's
memory, the memory of the plan being worked inside, and the employee's own
private memory. Every backend applies it to the rows it is about to return -
including backends that already expressed it in their own query language.

That looks like a double check and is a deliberate one. The SQL is an
optimisation; `visible()` is the rule. An index that drifts from it returns
fewer rows rather than another employee's.

## Consequences

* Replacing FTS5 with pgvector is replacing `infrastructure/memory/sqlite.py`.
  Nothing in `application/` changes, which is the Definition of Done for the
  phase and is checked as a test rather than asserted here.
* Memory is optional at every level. `Container.memory` is `None` when the flag
  is off, the runtime takes both halves as optional dependencies, and a machine
  without memory runs the loop it ran in Phase 8 - not a degraded Phase 9 one.
* Remembering cannot fail work. Every write and every recall is guarded and
  logged; a broken store makes a run slightly worse, never shorter.
* Memory rows carry no foreign key to `tasks` or `employees`. Memory is written
  *about* a task and outlives it, and keying it to the record would mean that
  clearing history erases what was learned from it.

### What is remembered is decided before it is stored

Two rules, both of which cost a validation run to learn (validation/tasks/phase-09-*):

* A finished task is **distilled** into a statement of fact before it is kept. A
  model's closing message is written for the person who asked; stored as it
  stands it reads as narration, and a later run given narration plans
  archaeology. One cheap call per task buys a memory that is worth recalling.
* A **standing preference** and **this request's parameters** are read as
  separate fields and only the first is kept. They look identical - "always
  answer in Markdown" and "in the sales folder" - and behave nothing alike: a
  preference has no expiry, so a parameter kept as one points every later
  request at this request's folder.

And one about who is told: memory is recalled **once per objective, before the
request is read**, and given to the reading, the decomposition and every task.
Handing it only to the employees leaves the one stage that has to resolve "the
same again" unable to.

## Alternatives considered

**A `MemoryStore` with a query language of its own.** More expressive, and it
would have put SQL-shaped strings in `application/` under a different name. The
question a caller actually asks is "what do I know about this, as this
employee", and `MemoryQuery` is that question with nothing else in it.

**Scope as a filter each caller passes.** One line shorter at every call site,
and wrong the first time somebody forgets it. A rule enforced where the rows are
cannot be forgotten by a caller.

**Vector search now.** The plan is explicit that it waits for PostgreSQL (§7 of
the plan's triggers). Local memory is small, and a full-text index over a few
thousand short items is not the thing that will be too slow.
