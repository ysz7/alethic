# ADR 0012 - Context between employees passes only along declared edges

**Status:** accepted (Phase 12)

## Context

Until Phase 12 a plan ran one task at a time, and each finished task's summary
was appended to a context that every later task received. That was simple, it
worked, and it is *sharing by default* with extra steps - the thing §86 says the
platform must not do.

The cost is not hypothetical. By the fourth task of a six-task plan the context
carries five summaries, four of them about work the fourth task has nothing to
do with, and the employee pays for all of them in the only currency a run has.
Worse, it is unbounded in the wrong direction: the more people work on an
objective, the more each of them knows about the others, which is the opposite
of what specialisation is for.

Phase 12 also had to run independent tasks at once, and that made the old
arrangement incoherent as well as wasteful. Carrying results forward is
inherently sequential: it asks what "everything so far" means for two tasks
that started at the same moment, and there is no honest answer.

## Decision

**A task receives the results of the tasks it declares it depends on, plus one
baseline the manager chose for the whole objective, and nothing else.** One
object owns this - `application/workforce/coordinator.py` - and the supervisor
has no other way to build a `SharedContext` for a task.

The decision was already written down. The planner emits dependency edges, and
an edge is precisely the statement "this task needs that task's result". §86
asks for context to be shared intentionally; the intention exists, and this
reads it instead of asking for a second one.

Three consequences follow, and each rejects an alternative that looked easier.

**Direct dependencies, not transitive.** In a chain t1 -> t2 -> t3, t3 gets t2's
result and not t1's. The transitive closure of the last task in any connected
plan is the whole plan, which is the default this exists to remove. If t1's
finding matters to t3, it is in t2's answer - and if it is not, t2 did its task
badly, which is a fact worth surfacing rather than papering over.

**There is no channel between employees (12.5).** An employee never addresses
another, never reads another's transcript, and never learns that another exists.
Employee-to-employee communication "strictly through the coordinator" is not a
rule anybody has to remember: there is nothing else to communicate through.

**A wave of independent tasks all see the same context.** They started together
and nothing connects them, so what one of them produces cannot reach another in
the same wave. That is more correct than the sequential behaviour it replaces,
where task two's context depended on whether task one happened to be listed
first.

## Alternatives rejected

**Keep carrying everything forward, and just run tasks in parallel.** The
context would then depend on scheduling - two runs of the same plan would give
different employees different information - and a plan's results would be
irreproducible for reasons nobody could see in the plan.

**Let Prometheus choose per task what to pass down, with a model call.** A judgement
call per task, paid for per task, to re-derive something the plan already
states. It also fails in the expensive direction: a manager that under-shares
produces a task that cannot be done, and it would have no way to find out.

**Give employees a message bus.** It is the design every multi-agent framework
reaches for, and it makes §86 unenforceable: any employee could ask any other
for anything, and "context is shared intentionally" becomes a convention.
