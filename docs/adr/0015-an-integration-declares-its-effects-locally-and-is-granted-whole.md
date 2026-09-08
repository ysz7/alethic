# ADR 0015 - An integration's effects are declared locally, and it is granted whole

**Status:** proposed (Phase 14)

## Context

Every capability the platform has so far was written here. A tool is a file
under `infrastructure/tools/`, its author declares an `Effect`, and ADR 0010
turns that declaration into a risk level nobody can lower. The whole governance
layer rests on that declaration being made by somebody inside the repository.

An MCP server breaks that assumption in one specific place: the tools arrive at
runtime, from a process the platform did not write, describing themselves. A
Gmail server offers `search_threads` and `send_message` in the same list, in the
same shape, with the same kind of sentence attached. Nothing in the protocol
distinguishes them in a way the platform may rely on, and §24 is explicit that
it must not try: a server's own metadata is untrusted input.

Two questions follow, and they have to be answered before any MCP code is
written, because both decide the shape of it.

**What is a discovered tool's effect?** Taking it from the server is the obvious
answer and the wrong one: a server that declares `send_message` as a read walks
straight past the approval gate, and the failure is silent and in the worst
direction. Declaring everything HIGH is safe and unusable - every search of a
mailbox becomes a question, and a user asked forty questions stops reading them,
which is the same failure with extra steps.

**Who may call it?** Least privilege says an employee gets what it lists and
nothing else, and `ToolRegistry` enforces that before a call is built. But an
integration's tool names are not known when the employee's declaration is
written, and they change when the server is updated. Requiring the user to write
`gmail.send_message` into a YAML file is a rule that is either edited by hand
after every server update or quietly abandoned.

## Decision

### The effect is local data on the Integration, never the server's word

An `Integration` record carries an effect map: tool name to `Effect`. It is
written on this machine, stored in this machine's database, and it is the only
thing the policy layer reads. The server's own annotations may seed the map that
is *proposed* to the user at discovery, and may never be what is stored without
somebody having seen it.

**Anything undeclared is EXECUTE.** A tool discovered after the map was written
- a server update adding one - is HIGH by ADR 0010's table, and therefore asks.
The conservative default is on the side that costs a question, because the
alternative costs a sent email.

This keeps the `ToolSpec` contract exactly as it is. An MCP tool is built with
`Effect.SEND` the same way `fs.write` is built with `Effect.WRITE`, the risk
follows the same table, and `ApprovalGate` never learns that a tool came from
somewhere else.

### A grant is per integration, and it is still a declaration

An employee declares `integrations: [gmail]`, not a list of tool names. The
runtime expands that to whatever the integration currently offers, and
`ToolRegistry` continues to enforce the expanded set exactly as it enforces
`allowed_tools` today.

This is the smallest thing that can be true at once: the grant is explicit and
recorded, so nothing is available to an employee nobody granted it to; and it
survives a server update, so the permission does not rot. The UI writes the
grant, so the user never edits the file - but the file is still what is
enforced.

The rejected reading is the ambient one: a connected integration usable by every
employee. It is how a single-agent product works and it cannot work here,
because the workforce is the point. An `organizer` granted files would silently
acquire the ability to send mail, and the declaration that said it may not would
still be sitting in its file, true-looking and dead.

### An integration contributes capabilities, and that is how work reaches it

A grant adds the integration's declared `Capability` values to the employee that
holds it. Without that the manager never routes mail work to whoever has mail:
`capabilities` is what `find_by_capability` searches, and an ability that is not
declared is work that never arrives (ADR 0008). The capability vocabulary stays
a closed enum - a routing term that any integration can invent is a term no
employee can be checked against.

### Discovered tools are cached, and connecting is lazy

What a server offers is written to the database at discovery. Listing tools,
validating an employee declaration and planning a task read the cache; a
subprocess is started when a call is actually made. Otherwise `alethic tools`
spawns every configured server in order to print a list, and an employee
declaration cannot be checked on a machine where a server is not running.

### Nothing below the tool boundary learns the word MCP

`application/` asks for a capability and gets a `Tool`. The protocol, the
transport and the server's lifetime live in `infrastructure/mcp/`, behind an
optional dependency, exactly as Playwright lives behind `--extra browser`. The
planner has no branch on where a tool came from; if it ever needs one, this
decision has failed.

### A result from an integration is data

An MCP result becomes an `Observation` and goes back to a model. Mail bodies,
issues and documents are the exact content §25 is about, so they are framed as
untrusted content at the transcript boundary rather than trusted to be inert.
An instruction found inside a result never changes a policy, a grant, an
approval requirement or a credential - those live in the store and in the
declaration, and no path from a tool result reaches them.

## Consequences

* Connecting a server is safe by default and imprecise by default: until
  somebody classifies its tools, everything but the ones they classified asks.
  That is the trade this accepts.
* Removing an integration removes its tools from the registry and its grants
  from effect, and leaves every audit line and task record standing. A record
  outlives what it describes (ADR 0010).
* An employee that declares an integration this machine does not have keeps
  loading, with a warning - the existing rule, since the machine may simply be
  configured differently (ADR 0008).
* `ToolSpec` gains a way to be built from a foreign JSON Schema. The parameters
  still become `Param` values, so argument coercion and `ignored_arguments`
  apply to discovered tools as they do to written ones; a spec carrying a raw
  schema and no parameters would disable validation for precisely the tools
  that deserve it most.

## Alternatives considered

**Trust the server's own read-only and destructive hints.** They are advisory in
the protocol and written by the party whose actions they describe. Useful as a
proposal to a person, worthless as an authority.

**Infer the effect from the tool's name.** `send_message` is obvious and
`trash_message` is not, and the first server that names a delete `archive` makes
the heuristic a security hole nobody can see.

**Grant individual tool names.** Precise, and it turns every server update into
a YAML edit that nobody makes. The permission that is never updated is the
permission that stops matching what the employee actually needs.

**Grant every connected integration to every employee.** The single-agent
model. It deletes the distinction the workforce is built on, and it deletes it
silently.

**Let an integration declare new capability names.** Free-form routing terms
mean an employee's claim can no longer be checked against anything, which is the
one thing `domain/employees/validation.py` exists to do.
