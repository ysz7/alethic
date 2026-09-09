# ADR 0018 - A connected service is a routing term of its own

**Status:** proposed (Phase 18)

## Context

Work is routed by declared capability. The plan says what each task needs, the
registry answers who offers it, and the delegator narrows the field before a
model is shown anything (ADR 0007, ADR 0008). The vocabulary is
`domain.capabilities.Capability`, a closed enum, and it is closed on purpose:
a model, a tool, an employee and a plan all declare into it, and a term one of
them can invent is a term the others cannot be checked against.

Phase 14 connected external services and made everything they offer an ordinary
`Tool` in the ordinary registry (ADR 0015). A grant is per integration, and it
contributes the integration's `granted_capabilities` to the employee holding it
so the manager can still route by capability. That is where the closed
vocabulary stops working, and the failure was measured rather than predicted:

* the notes server can only be granted `FILE_ACCESS`, because there is no term
  for "notes" and there never will be;
* four of the five employees that ship declare `FILE_ACCESS`, because reading a
  file needs it;
* so "search my notes for what we said about shipping" narrowed to four people
  and was handed to the one that can run code, which searched for the notes with
  a Python script and was refused.

The refusal was correct. The routing put it there. Phase 14 recorded this and
left it open, with the workaround of granting the service to everybody who might
be given the work - which is not least privilege and not routing.

## Decision

**A task may require a service by name, as well as a capability.** The two are
separate axes of one question - *what must this person be able to do*, and
*what must they hold* - and `domain/workforce/routing.py` is the value that
carries both. `CapabilityRequirement` is unchanged and still describes work a
model can be asked to do; a model holds no connected services, and one field
there that is meaningless in half its uses is how a vocabulary stops being one.

**The names come from the workforce, not from the platform.** The planner is
shown, on each employee's card, which services that employee was granted, and a
term in `needs` that is not a capability is kept only when somebody in this
workforce holds a service by that name. An invented one is dropped exactly as an
invented capability is.

**It can only narrow.** `holders` filters candidates and never adds one, and
holding a service grants no tool the grant did not already grant. A service
nobody holds widens back to the previous field rather than failing the task,
which is the same rule capability narrowing has always followed: a task routed
imperfectly beats a task routed nowhere.

## Consequences

An integration no longer has to borrow a capability in order to be reachable.
`granted_capabilities` stays - it is still how a service says that work of a
*kind* can reach it, and it is still declared locally rather than by the server -
but it is no longer carrying weight it cannot bear.

The capability vocabulary stays closed, which was the point of keeping it. What
changes is that it is no longer the only thing routing can say.

The cost is one more term a plan can get wrong. It is bounded in the same way
every other routing term is: what the model writes is checked against what the
workforce declares before it narrows anything, and a wrong term narrows to
nobody and is discarded rather than obeyed.

The obvious alternative - opening the capability enum so an integration can
invent a term - was rejected for the reason the enum exists. An employee
declaration is validated against the capabilities that exist here
(`domain/employees/validation.py`), and a vocabulary any connected server can
extend at runtime cannot be validated against anything.
