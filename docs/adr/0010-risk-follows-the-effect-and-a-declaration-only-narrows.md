# ADR 0010 - Risk follows the effect, and a declaration can only narrow

**Status:** accepted (Phase 10)

## Context

Phase 4 asked each tool to declare a `RiskLevel` and gated anything at HIGH or
above on a person. That was the right size for four tools and does not scale.
`RiskLevel.MEDIUM` on a new tool is a number somebody chose, the next author
choosing differently is invisible in review, and the failure is silent in the
worst direction: a tool that sends mail, declared MEDIUM, sends mail without
asking. §70 already states the rule the numbers were meant to encode - reading
is low, writing is medium, sending, spending, deleting and publishing are high -
but it was stated in a document, and a rule in a document is not enforced.

Phase 10 also has to make `policies:` mean something. Four employees have
declared `no_irreversible_actions` since Phase 8 and nothing has ever read it.
A declaration that is not enforced is worse than no declaration: it reads in the
file as a restriction that is in force.

And §67 is explicit that policies never live inside prompts. "Never send email"
in a system prompt is a suggestion a model weighs against everything else it was
told; `EMAIL_SEND = REQUIRE_APPROVAL` is a value a test can assert on and a
model cannot argue with.

## Decision

### The tool declares what it does; the platform decides what that is worth

`ToolSpec` carries an `Effect` - READ, WRITE, EXECUTE, DELETE, SEND, PUBLISH,
SPEND - and `domain/policies/risk.py` maps it to a level. A tool author knows
exactly what their tool does to the world and should not also have to know what
this platform considers risky about it, because that is a policy decision and
policy decisions belong in one place.

`ToolSpec.of` takes the higher of the declared level and the effect's, so a spec
may raise what its effect implies - a read of something sensitive is a real case
- and can never lower it. That is enforced where the spec is built rather than
left to review.

### One engine, two kinds of rule, and only one of them is optional

`domain/policies/rules.py` is a pure function over a `PolicyRequest`: no clock,
no settings, no database. The same action decided twice decides the same way,
which is what makes an audit line worth reading.

Two kinds of rule meet in it and they are not interchangeable:

* the **threshold** applies to everybody and comes from the risk table alone. At
  HIGH and above a person decides. No declaration removes it.
* a **named policy** is what one employee opted into, and it can only narrow.
  `read_only` denies what the threshold would have allowed; nothing in the
  catalog widens anything.

Rules are resolved by severity - DENY beats REQUIRE_APPROVAL beats ALLOW -
rather than by declaration order, so what a file does cannot depend on how it
was typed.

### A denial is not a question

Risk alone can only ever produce "ask". A declared policy can produce "no", and
when it does the user is not offered the chance to allow one call of it. Putting
it to them would turn the declaration into a suggestion, which is the failure
this phase exists to fix.

### An unknown policy name fails the declaration

The engine ignores a name it does not recognise, so `no_sendng` would be a
restriction that reads as enforced and is nothing at all.
`domain/employees/validation.py` reports it as an error - wrong on every machine
- and `alethic employees --strict` exits non-zero on it. A wrong tool name loses
an employee a tool it can see it does not have; a wrong policy name loses it a
restriction nobody can see is gone.

### Least privilege stays in the registry

The engine does not re-check whether the actor was granted the tool.
`ToolRegistry` already refuses one it was not, before the call is built, and a
second check here could only ever disagree with the first - silently.

### The audit records what has no other trace

`audit_log` is not `tool_calls` renamed. `tool_calls` is accounting: what ran,
how long, what came back. `audit_log` is accountability: who asked for what, and
what was decided. They agree on a successful call and diverge exactly where it
matters - a denied action has an audit line and no tool call, because the tool
never ran, and that is the line an audit exists for. So the gate records the
refusals, the executor records what ran, and neither records the other's half.

The table carries no foreign keys. A record outlives what it describes; keying
it to `tasks` would mean clearing history erases the record of what was done to
the machine.

### A question can have a deadline

An unanswered approval leaves a PENDING row, and a PENDING row is a task
`alethic resume` keeps picking up - so a question nobody ever answers is a run
that never finishes. Expiring is a refusal like any other: the rule that an
unconfirmed action does not happen covers "nobody was there" as much as "they
said no". Expiry is applied where the rows are, because the process that asked
is usually gone by the time the deadline passes.

A synchronous confirmer - a terminal - is never timed out. Somebody is standing
there, and taking the prompt away while they read it would be worse than
waiting.

### A workflow is a declaration and runs through the same runtime

`WorkflowEngine` decides nothing about how work is done. It resolves a declared
dependency graph and hands each step to `StepExecution` - the contract the
manager uses for the same purpose - so a predefined process and a plan Alethic
invented differ in where the decomposition came from and in nothing below it.
Adding one is adding a file under `workflows/`, and
`tests/e2e/test_governance.py` proves it by declaring one in a temporary
directory.

Retry lives on the step, not on the engine: fetching a page again is free,
sending a message again is not, and an engine-wide count would have to be set
for the least forgiving step.

## Consequences

* Adding a tool means answering "what does this do to the world", and the risk
  follows. Getting it wrong is now a wrong answer to a question with seven
  possible values, not a number nobody reviews.
* `alethic policies` prints the table and the catalog with who opted into what,
  because a policy documented in prose and absent from the catalog enforces
  nothing.
* The four shipped employees keep behaving as they did:
  `no_irreversible_actions` restates the threshold for them, and now does so as
  an enforced rule rather than an unread field.
* `alethic audit` shows the actions that did not happen, which is the list that
  did not exist before.

## Alternatives considered

**Keep the hand-declared level and add a lint.** A lint would have to know which
effect each tool has in order to check the level, at which point the effect is
the declaration and the level is derived - which is this decision, with an extra
file.

**Make `policies` able to grant as well as restrict.** It would let one employee
be trusted with something the platform asks everybody else about. It would also
mean a declaration could quietly raise its own privileges, and the file that
grants it is the file the employee's author writes.

**A policy DSL in the YAML.** Expressive, and it puts a small programming
language in a declaration nobody tests. The catalog is seven named rules; when
an eighth is needed it is a function in `rules.py` and a test next to it.

**One table for tool calls and audit.** It would mean either inventing a tool
call that never happened for every denial, or losing the denials. Both lose the
half that matters.
