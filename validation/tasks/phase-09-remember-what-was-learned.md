# Phase 9 validation - the second request is one the first made answerable

**Capability under test:** memory. What a task learned, what a plan produced and
how the user wants work done, recalled into the context of a later run - through
one contract that hides the store.

**Definition of Done:** *changing the memory backend changes no line in
`application/`; vector search is not introduced while full text suffices; `grep`
over `application/` finds neither `memory_items`, nor `MATCH`, nor `fts`.*

**Validation task:** a repeated task goes noticeably better than the first,
because of the context that accumulated.

## How it was run

The DoD is a claim about the codebase and is checked as a test:
`tests/unit/test_memory_access_rule.py` reads every source under `domain/`,
`application/`, `app/`, `employees/` and `prompts/` and fails on any mention of
the table, the index or its query language.

The validation task is a claim about behaviour and was run against real models -
the shipped `models.anthropic.toml`, `claude-sonnet-5` for planning and
execution, `claude-haiku-4-5` for verification, extraction and the two things
this phase added to the model budget (distilling an outcome, consolidating
episodes).

Two folders of small CSVs in the workspace, `sales/` and `returns/`, identical
in shape. Two requests, in two separate processes, with the database kept
between them:

```bash
uv run kai ask-kai "Summarise what is in the sales folder and write summary.md. Always answer in Markdown."
uv run kai memory
uv run kai ask-kai "Do the same for the returns folder."
```

The second request is the whole test. *"Do the same"* names nothing: without
memory there is no record anywhere of what "the same" was, and the platform has
no conversation to look back at - `ask-kai` is one process per request.

## Result - passed, 2026-09-07

### 1. The second request was resolved, and the work was done

**A:** `[DONE] $0.199, 2m14s` - three files listed and read, figures computed
with `code.run`, `summary.md` written and read back.

**B:** `[DONE] $0.490, 4m05s` - `returns/` listed and read, its figures computed
(27 units, $235.50, 4 rows, 2026-07-22 to 2026-09-06 - checked by hand against
the CSVs and correct), `returns/summary.md` written to match `sales/summary.md`'s
structure section for section.

Nothing in run B's request said what to do. The plan went straight at the
returns folder, and the employee was told the structure to match. That is memory
doing the only job that cannot be done without it.

### 2. And every stage was reading it

```
memory.recalled  employee=analyst  items=4
```

`kai memory` after run A shows what the second run was working from - and shows
the shape of what is kept:

```
SEMANTIC   The user prefers: Always answer in Markdown
EPISODIC   The `sales` folder on this machine contains three files: `README.txt`,
           `2026-q3-north.csv`, `2026-q3-south.csv`. The two CSVs hold 7 rows of
           sales data spanning July-September 2026...
```

Those are statements about the machine, not a work log. Getting them that way
took three attempts, and what the first two produced is the substance of this
write-up.

### 3. What running it found - four defects, all in this phase's own code

**A request's parameters were being remembered as standing preferences.** The
intent reader returns `constraints`, and the first version stored all of them
forever: `"The user asks that input_location: sales folder"`. On the next
request that came back as a workspace fact and pulled the plan towards `sales`
while the user had asked for `returns`. Fixed by asking for the two separately -
`prompts/kai_intent/v1.md` now distinguishes a standing preference ("always
answer in Markdown") from a parameter of this request, and only the first is
kept. `tests/unit/test_kai_memory.py` holds the case.

**What was stored was the model talking, not what it found.** `record_task` kept
the employee's closing message, which is written for the person who asked and
reads like this a week later: *"Perfect! Now I have everything I need. ## Task
Complete **File created:** summary.md (3,248 bytes)"*. Handed to the next run as
what this workspace knows, it reads as a record of somebody writing reports -
and the next plan was a report about a report. `application/memory/distiller.py`
now turns each finished task into two or three sentences of fact with one cheap
model call, falling back to the raw text if it cannot be reached. This is the
one place in the recorder where a model call per task is worth it: the
alternative is not a worse memory, it is a misleading one.

**The manager planned without memory.** The recalled context reached the
employees - through `SharedContext.facts` - and not the decomposition, which is
the one stage that has to know what "the same" refers to. Given the second
request, KAI wrote a task to *go and find out what had been done before*: an
entire employee run spent on archaeology, twice, with two different models.
Memory is now recalled once per objective, before the request is read, and
given to the reading, the plan and every task. That single wiring change is what
turned run B from ESCALATED into DONE.

**The analyst did not know its own tools.** `code.run` runs in a throwaway
directory with no access to the workspace - deliberately, since Phase 4, because
that is what makes running generated code allowable at all. Nothing told the
analyst, so every run spent two or three steps discovering it by failing. Fixed
in `employees/analyst/prompts/system.md`: read with `fs.read`, carry the data
into the script, write results back with `fs.write`. Like Phase 8's finding, the
fix was a declaration rather than code.

## What this does not prove

**The second run was not cheaper - it was correct.** $0.49 against $0.199, and
four minutes against two. The saving memory produced was not in tokens: it was
that a request which is unanswerable on its own got answered at all, and matched
the earlier output's structure without being told it. The plan's phrasing - that a
repeated task goes noticeably better - holds for correctness and not for cost,
and recall's own cost is real - six recollections in every prompt, plus a distiller
call per task.

**Small models make this worse, not better.** The same pair on
`claude-haiku-4-5` throughout escalated in three runs out of four - not on
memory, but on the verifier refusing results whose evidence the employee had not
quoted. Memory adds context to a prompt, and a model that was already struggling
to follow a longer prompt struggles more.

**Nothing decides that a memory has become false.** A preference is superseded
by another preference; a stale fact is caught only by the employee checking it,
which is why recall is presented as recollection rather than fact. There is no
contradiction detection here.

**Consolidation was never triggered.** It folds the oldest episodes once twelve
accumulate, and these runs produced six. What happens to a workspace with a
thousand memories is untested, and the ranking cutoff that keeps recall usable
at that size is a guess until it is run.

**One workspace, one machine, four employees.** Nothing here exercises two
employees reading each other's plan memory during one objective, which is what
Phase 12's parallelism will do to this design first.
