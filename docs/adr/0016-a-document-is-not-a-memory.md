# ADR 0016 - A document is not a memory

**Status:** accepted (Phase 15)

## Context

Phase 9 built memory: what a task learned, what an employee found out about
reaching its work, how the user likes things done. All of it is written by the
platform about itself, and all of it is reached through `Memory.recall` - the
one search path, enforced by a test that fails the build if anything names
`memory_items`, `MATCH`, `fts5` or `bm25` (ADR 0009).

Phase 15 adds something that is not that: a file the user brought. A contract, a
specification, the minutes of a meeting. It is text, it is searched, it is put
in front of a model, and it is scoped to a workspace - which makes
`memory_items` look like exactly the right table for it.

It is not, and the two reasons are the shape of this decision.

## Decision

### Knowledge is stored apart from memory, with its own contract

`domain/knowledge/` holds `Document`, `Chunk`, `KnowledgeStore` and `Retriever`.
Nothing about it is a `MemoryItem`, and `recall` does not return chunks.

**Memory decays and expires; a document does not.** `domain/memory/ranking.py`
gives every kind a half-life and a time to live, because a working note is worth
little by tomorrow and an episode is worth less each week. A specification the
user uploaded is worth exactly as much in March as it was in January, and
storing it in a table whose maintenance job deletes rows by age would mean the
platform quietly throwing away something a person put there on purpose. The
prune that keeps memory bounded is correct for memory and destructive for
knowledge.

**Memory is recalled; knowledge is cited.** A recollection reaches a prompt as
"you noted last time that the report was in reports/q3.md" - deliberately hedged
(`application/memory/assembler.py`), because memory can be stale in a way an
instruction cannot. A chunk of a document is the opposite: it is a quotation,
and the useful thing about it is *which document and where*. Same table would
mean one of the two is rendered wrongly, and the one rendered wrongly would be
whichever was added second.

### They meet in the context assembler and nowhere else

`ContextAssembler` already puts a run's context together in order of trust: the
goal, what the manager passed down, then what was recalled. Retrieved knowledge
is a fourth source in the same place, labelled as what it is. That keeps one
answer to "what does this run know", and keeps the merge in the application
layer rather than inside a store that would then have to know about the other.

### Retrieval obeys Phase 9's rule even though it is a different contract

The index narrows, the domain decides. Nothing in `domain/`, `application/`,
`app/` or the prompts names a vector table, a metric or a library - exactly as
nothing today names FTS5. Ranking is `domain/memory/ranking.py`'s existing
formula with the retriever's score as its relevance term, so lexical and
semantic hits are comparable because they were normalised before the domain saw
them.

### A chunk records the model that embedded it

Name and dimension, on the row. Without it, changing the embedding model or
moving to another store leaves nobody able to say whether the existing vectors
are still comparable, and the answer becomes a guess. With it, a mismatch means
re-indexing, which is work; without it, a mismatch means silently comparing
numbers that mean different things, which is a wrong answer nobody can see.

### An uploaded document is untrusted content

It was written by somebody who is not the user, and an instruction inside it is
not an instruction to the platform. The framing built in Phase 14
(`domain/integrations/untrusted.py`) is applied to extracted text rather than
re-invented, for the same reason and against the same failure (§25).

## Consequences

* Memory keeps its maintenance, its decay and its TTL, and none of it can reach
  a user's documents.
* `prometheus memory` and a future documents view answer different questions and
  are not merged into one screen that implies they are the same thing.
* Deleting a document deletes its chunks and its vectors and leaves memory
  alone; pruning memory leaves documents alone.
* Two stores means two places a workspace boundary must hold. Both apply it in
  the domain, the way `domain/memory/access.py` already does.

## Alternatives considered

**One table with a `kind` for documents.** Cheapest to build and wrong at the
first prune: either knowledge inherits an expiry it must not have, or memory
loses the maintenance that keeps it bounded. Special-casing the kind inside the
maintenance job is the same decision as two tables, with the boundary written in
`if` statements instead of in the schema.

**Chunks as `MemoryKind.SEMANTIC` items.** They would then be returned by
`recall` into every prompt that assembles memory, hedged as recollections,
without the source they exist to cite.

**Retrieval as a method on `Memory`.** It would put a vector backend behind a
contract whose two methods are about remembering, and the first caller wanting a
citation would reach around it.
