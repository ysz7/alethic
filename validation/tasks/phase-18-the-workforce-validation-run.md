# Phase 18 validation - the workforce, given real work

**What was under test:** the one phase never closed by the platform's own rule.
Phase 12 built parallelism, a coordinator, acceptance on evidence and
reconciliation, and closed on unit tests against fakes. Its scenario,
`a-team-on-one-objective`, had been run four times, had passed twice, and had no
report. Three claims rested on nothing but those tests: context passes only
along declared edges, a result is accepted on the evidence rather than on the
report, and contradictory reports are resolved or escalated rather than blended.

Sixteen recorded runs later, five things the suite agreed with turned out to be
wrong. Every one of them was invisible to 1082 passing tests, and every one was
found by running the same request twice.

Model: `gemma4:31b-cloud` for the work that decides things, `lfm2:24b` and
`lfm2.5:8b` for the small structured jobs. No key, no spend.

## What the runs found

### The manager answered out of a memory of the last run

Three consecutive runs of the same request - "read both and leave me
`figures/comparison.md`" - were closed with no plan, no task, no employee and no
file. The intent read came back `needs_work: false` each time, and the objective
verifier passed the answer.

It was not variance. The three earlier runs had left a workspace memory saying
*"the price comparison document at figures/comparison.md reports that our
Starter tier is 5.00 EUR lower..."*. The scenario's `reset` had deleted the file
before the run; memory does not know that, and nothing asked it to.

Phase 11 recorded this failure once already, and the countermeasure was "a
direct answer faces the same verifier as delegated work". It did. The verifier
was handed a fluent paragraph and a list of criteria, and the paragraph met
them: what separates a real result from an accurate description of one is not in
the text.

**Fixed the way Phase 16 fixed it for tasks, one level up.** The objective
verifier is now shown what the platform recorded as having happened, and a
direct answer's record is that there is none - said in a full sentence rather
than left as an empty heading (`NOTHING_WAS_DONE`, `alethic_verifier/v3.md`).
The rule beside it is that a criterion asking for something to *exist* is unmet
unless that section shows it being made. `alethic_intent/v5.md` says the other
half in the reading: what you remember is not what is there, and resolving a
reference to earlier work is not doing the work again.

Two later runs rejected the direct answer with the words *"no file system
changes occurred"*, which is the check working out loud.

### Recovery read a refusal out of a sentence

`classify` decides what a failed task calls for, and the platform's rule is that
it is decided by the kind of failure and never by message text. It was matching
`"may not use"` in an observation's summary.

That is text, and it is also only half of what refused means.
`domain/tools/refusals.py` states both: a call is refused when the employee may
not have the tool *or when a person said no*. The gate's refusals - the ones
Phase 10 exists for - were invisible to it. A task the person at the keyboard
declined was read as a bad plan, replanned into the same task, given to the same
employee, and declined again.

Now it reads `details["refused"]`, which the executor has written all along.
Reassignment would have saved the run it was found in: the work was reading two
small files, and three of the five employees could have done it without asking
anybody.

### Who does the work was decided by the cheapest model in the catalog

`CapabilityDelegator.routing()` returned `TaskKind.EXTRACTION` with no quality
floor, and the configured default for extraction is the smallest entry in the
catalog. So the decision that commits an entire employee run - its budget, its
tools, its whole route through the world - was made by an 8B model reading five
cards.

It handed "create a short Markdown document at figures/comparison.md" to the
employee that had just done the analysis, with a reason about data analysis,
past the one whose entire declaration is turning findings into documents. It did
that in every run: three plans, six tasks, one employee.

`MIN_DELEGATION_QUALITY` is a floor, stated as a *requirement* rather than a
hint for the reason verification's is (ADR 0003) - hints only rank what survives
the filter, and the configured default beats them. Three runs after it, the
scenario passed three times out of three, and the second task went to the writer
every time.

### The scenario could not fail for the reason it was written

`a-team-on-one-objective` passed twice while one employee did both ends of its
own two-task plan. Every check it declared was about the file, and a file says
nothing about who wrote it. A claim nothing can falsify is not a measurement.

`Expectations.min_employees` is the fix: the only expectation in the set about
*how* a result was arrived at. Two rather than three - the request has three
jobs in it and merging the two readings is a defensible plan, while giving the
gathering and the writing to one person has not divided the work at all.

### The task verifier judged work against its own plan

The employee planner wrote a step to read a file that does not exist; the
employee searched the connected service instead and found what was asked for;
the verifier failed it for "relying instead on a general search". The plan is a
means, and nothing in the prompt said so. `prompts/verifier/v4.md` says it: a
result that meets the task by a route the plan did not name has passed.

## What was built for the finding Phase 16 handed on

Routing with an integration connected, `use-a-connected-service`, 0/4 before
this phase and never once passed since it was written.

The cause was already known and correctly described in Phase 14's report: the
capability vocabulary is a closed enum, every term in it is claimed by an
employee that ships with the platform, and a notes server can therefore only
declare `FILE_ACCESS` - which four of the five employees offer. The work went to
whichever of them the delegating model liked, and the analyst searched somebody's
notes by running a Python script and was honestly refused.

**A connected service is now a routing term of its own** (ADR 0018,
`domain/workforce/routing.py`). A task's `needs` may name a service as well as a
capability; the names come off the workforce cards, so a term nobody holds is
dropped exactly as an invented capability is; and it can only narrow. The
capability enum stays closed, which was the point of keeping it - it is simply
no longer the only thing routing can say.

Four runs, four times routed to the one employee holding the grant, with no
model call at all: **"the only employee that declares notes"**. The scenario
passed for the first time. It failed the other three times for reasons that have
nothing to do with routing - one of them the verifier defect above, two of them
the model inventing a source name or refusing to believe a file it was told was
written.

## The queue of prompts showing a filled example is empty

Five prompts still showed a form with values in it, held back because replacing
one is a behaviour change that has to be measured rather than assumed, and a
validation run was already happening here. All five were rewritten:
`alethic_planner`, `alethic_delegation`, `planner` and `screen_reader` lost their
examples and gained prose describing the shape of an entry.

`alethic_reconciliation` was the interesting one. Its single value was
`"consistent": true`, and that was the deliberate side to copy - an unreadable
answer must mean *consistent*, because a check that escalates whenever its model
stutters teaches the user to ignore it. Emptying the form meant dropping the
field, which is a contract change: consistency is now read off the list of
contradictions being empty, the list was always the specific claim, and the safe
answer and the empty form are the same answer. `KNOWN_UNFIXED` is now an empty
frozenset and may only shrink.

## What is still not confirmed

**Nothing has run in parallel.** Every wave in every run was one task wide. The
supervisor starts everything `Plan.ready` returns and there was never more than
one, because the plans this workforce is given are chains: read, then write. The
width is a property of the decomposition and not of the executor, and the
planner prompt now says in as many words that two readings of two sources are
two tasks depending on nothing. It still chains them. `MAX_PARALLEL_TASKS`,
`WorkforceCoordinator`'s edges and `asyncio.gather` remain confirmed by unit
tests only.

`alethic.wave` was added for this - the trace could not answer "did anybody
actually work at the same time" - and its first job was to say no.

**Reconciliation has never fired on real work.** It needs two succeeded reports,
and the plans that produce two both make the second depend on the first, where
disagreement is not available. Escalating a contradiction is still a claim
resting on fakes.

**Acceptance on evidence never had to refuse anything.** No run produced a task
that reached for tools, had every one refused, and still reported success -
which is the case `domain/workforce/acceptance.py` exists for.

**`alethic employees` says an integration's tools are not offered here.**
Listing must not start a server, so the tool registry has not been given them at
that moment, and a correct declaration reads as a broken one. Cosmetic, and it
is the second time this listing has told somebody something untrue about a
grant.

## What the suite says now

One full pass after every fix above: **8 of 13**, and for the first time since
the report has existed there is nothing under "does not work at all".
`use-a-connected-service` moved out of it, `triage-an-inbox` and
`remember-what-was-learned` passed, and `operate-a-screen` is skipped because
the desktop is off here.

The aggregate percentage in `validation/REPORT.md` went *down*, from 62% to 58%,
and that is not a regression. Eighteen runs of `a-team-on-one-objective` are now
in the record, and most of them were made deliberately against broken
intermediate states while looking for the five defects above. The report counts
every attempt ever recorded on this machine, which is the property that makes
one pass read as SOMETIMES; it also means a phase spent hunting is a phase that
lowers the number. The per-scenario lines are the ones to read.

The last three runs of the scenario before the full pass were three passes.
The one inside the full pass failed, and correctly: that plan asked for CODE,
only one employee declares it, `code.run` is EXECUTE and therefore HIGH, and the
scenario declares that the person at the keyboard would have said yes to
`fs.write` and nothing else. The brake held. Whether this scenario passes now
turns on whether the decomposition asks to run a program in order to compare two
numbers, which is a question about the plan and not about the workforce.

## Verdict

`a-team-on-one-objective`: **works**, on the evidence of three consecutive
passes after the delegation floor, with two employees each time and the
`min_employees` check standing behind the claim.

`use-a-connected-service`: **works sometimes**, and its routing works every
time. The remaining failures are the model, not the platform.

Phase 12's Definition of Done is met for delegation, hand-off and acceptance,
and **not** for concurrency: the machinery is there and nothing has yet given it
two things to do at once.
