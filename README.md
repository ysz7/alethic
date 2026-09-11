# Prometheus

A **local-first** platform where an AI manager runs digital employees that do
real work on your own machine.

```
User -> Prometheus (AI Manager) -> Workforce -> Digital Employees -> Capabilities -> External World
```

No server, no cluster, no account. You clone the repository, add a provider key,
and give Prometheus a task.

## Status

**Phase 15 - Knowledge, memory and workspaces.** Work and personal are two
workspaces now rather than one heap: each has its own files, its own documents
and its own history, and switching moves what the employees can see. You can
give Prometheus something to read - a contract, a specification, minutes - and it is
quoted back with its source rather than half-remembered; a question whose answer
is in another workspace's document gets "I do not know", which is the point.
Everything can live in PostgreSQL instead of the SQLite file, and moving there
copies, verifies row by row, and only then offers to erase what it came from.
Before it, **Phase 14 - Integrations:** Prometheus can be given services it did not
ship with, an MCP server is added in Settings, its capabilities become ordinary
tools, and what each one is allowed to do is decided on this machine rather than
by the server. Before that, **Phase 13 - Interface layer and the desktop application.** Every surface now
talks to one application-level boundary, and the desktop window is an adapter
over it rather than a second copy of the platform. Saying hello to it gets a
reply, in the language you configured, rather than a plan. Underneath it, Phase 10's
brake is a policy layer: what a tool does to the world decides what it costs to
do it, and an employee's declaration can narrow that further. Five employees,
not thirty:
`researcher` finds out what is true, `organizer` puts a folder in order,
`operator` works interfaces that have no API, `analyst` computes answers
from data on this machine, and `writer` puts the result into words. Each is a directory under `employees/` with no Python
behind it, and Prometheus routes work to them by what they declare they can do.

You state what you want. Prometheus works out what that means, decides whether it
needs doing at all or can just be answered, breaks it into tasks if it has to,
gives each one to whoever is declared for it, and checks the result against
criteria it wrote down before the work started.

Processes you already know the shape of do not need planning at all: a file under
`workflows/` names the steps and who does each, and runs through the same
employees and the same brake.

The employees do the work: read and sort files inside one working directory,
search the web, open a page and read it, run a short program under limits - and,
when none of that reaches the thing that has to be done, operate it on the
screen. Anything irreversible - overwriting a file, running generated code,
touching your desktop - waits for you to say yes, in the page or at the prompt.
And the second time you ask for something like the first, the work starts from
what the first one found out.

See `development/implementation-plan.md` for the full roadmap.

## Getting started

```bash
uv sync
uv run prometheus --version
uv run alembic upgrade head    # creates ~/.prometheus/prometheus.db
uv run prometheus config
uv run prometheus models              # the model catalog and its defaults
```

Copy `.env.example` to `.env` and set `PROMETHEUS_LLM_API_KEY`, then:

```bash
uv run prometheus ask "Which city is the capital of Germany?"
uv run prometheus spend               # what the calls have cost so far
```

## Asking for something

```bash
uv run prometheus ask-prometheus "Read my meeting notes and write decisions.md, one line per person."
uv run prometheus objectives          # what has been asked here, and how it went
```

You say what you want; you do not say who does it. Prometheus reads the request into
acceptance criteria, decomposes it only if it has to - a question it can answer
outright gets an answer, not a plan - picks an employee from what is declared,
and judges the result against those criteria before you see it. If it falls
short twice, you get the work that did succeed plus a plain list of what is
missing, rather than a confident summary of eleven things you asked twenty of.

Nothing in Prometheus names an employee. Add a directory under `employees/` and it is
offered on the next run; that is enforced by a test that reads the directory.
See [ADR 0007](docs/adr/0007-the-manager-decides-and-never-executes.md).

## Workspaces and documents

```bash
uv run prometheus workspaces                  # what exists here, and where you are
uv run prometheus workspace-new "Client A"    # its own files, documents and history
uv run prometheus workspace-use client-a
uv run prometheus document-add ~/policies/delivery.md
uv run prometheus documents
```

A workspace is a boundary rather than a label. Switching moves the one directory
the file tools can see, so isolation does not stop at the moment an employee
opens a file, and a run already going keeps the workspace it started in.

A document is not a memory. What the platform noticed about its own work decays
and expires; what you brought does not, and it is quoted with its source instead
of recalled as a lead. Search is by meaning as well as by words, and the model
that does the embedding runs on this machine by default - what is being embedded
is the contents of your documents. See
[ADR 0016](docs/adr/0016-a-document-is-not-a-memory.md).

## Where everything is kept

```bash
uv run prometheus storage                     # backend, and how much is in it
uv run prometheus storage-migrate --to postgresql://localhost/prometheus
uv run prometheus storage-migrate --to postgresql://localhost/prometheus --erase
```

SQLite by default: one file, no server between `clone` and `run`. PostgreSQL -
including Supabase, which is the same thing with a different connection string -
is a setting rather than a rewrite. Moving is three separate steps in one safe
order: copy, verify row by row against the destination, and only then, when you
ask for it and confirm what will be destroyed, erase the source. See
[ADR 0017](docs/adr/0017-storage-is-a-setting-and-moving-is-copy-verify-erase.md).

## The interface

```bash
uv run prometheus serve               # http://127.0.0.1:8765
```

One command and one process: the page, the employee runtime and the database are
the same thing. That is what lets a tool call stop on a question and carry on the
moment you answer it in the browser, with nothing queued and nothing polled.

Type a goal into the page and the same thing happens: Prometheus reads it, plans it and
hands it out. The trace shows the manager and its employees as one story - the
step, who is doing it, the tool, its arguments and what came back - as it
happens rather than after it. Approvals appear there, cost and result are on
screen, a run can be stopped, and every past objective can be opened again with
every plan revision it went through, including the ones it superseded.

It binds to loopback and has no password. Those are the same decision: this
surface starts tasks and approves irreversible actions, and it is safe without a
login precisely because nothing off your machine can reach it. See
[ADR 0006](docs/adr/0006-the-interface-runs-inside-the-process-it-watches.md).

Everything below still works from the terminal - a machine with no browser must
not need one.

## The desktop application

```bash
cd desktop && npm install && npm run tauri dev
```

A window instead of a tab: a greeting, a field, and what Prometheus is doing about
what you typed. It is an **interface**, not a second copy of the platform - it
talks the same local HTTP and the same event stream the page does, to the same
process, with the same database and the same running work. Nothing plans, calls
a model, drives a browser or approves anything in Rust or TypeScript.

The shell starts `uv run prometheus serve` for you unless one is already answering,
and leaves a runtime it did not start alone when the window closes. Details, the
environment variables and the frontend's own layout rules are in
[desktop/README.md](desktop/README.md).

Adding another interface later - a bot, a second window, a remote client - means
writing an adapter over `application/interface/`, not changing the core. That is
what the boundary is for:
[ADR 0014](docs/adr/0014-an-interface-is-an-adapter-over-one-application-boundary.md).

## Giving one employee a task directly

Still supported, and still the right thing for a script or a machine with no
browser - but choosing the employee is the manager's job, not yours:

```bash
uv run prometheus employees           # who is declared
uv run prometheus tools               # what this machine can do, and who may do it
uv run prometheus run-task --employee researcher "Explain what SQLite WAL mode changes about concurrency, with sources."
uv run prometheus resume              # pick up anything that was interrupted
```

Every task goes through three stages. **Plan** turns the goal into steps.
**Execute** runs a tool-calling loop bounded by three budgets at once - steps,
cost and wall time - and each action is followed by an explicit observation
rather than feeding raw output into the next decision. **Verify** judges the
result against the goal, and a task cannot complete without passing; a rejected
result goes back through planning once, told what was missing.

State is written to the task after every step, so `kill -9` mid-run loses
nothing: `prometheus resume` continues from the last saved step instead of starting
over.

## What it remembers

Ask for something twice and the second run does not start from nothing. What a
task learned, what a plan produced and what you said you wanted are recalled into
the context the next run plans from - as recollection, not as fact, so a memory
that has gone stale is checked rather than acted on.

That is what makes a request like *"do the same for the returns folder"* a
request at all: there is no conversation to look back at, and nothing but memory
records what "the same" was. What is kept is what was found out, not what the
employee said about finding it - each finished task is distilled into a couple of
sentences of fact before it is stored.

```bash
uv run prometheus memory                     # what this workspace remembers
uv run prometheus memory --search invoices   # and what it knows about one thing
uv run prometheus memory --prune             # drop what has passed its time to live
```

Four kinds of thing are kept, and they are kept differently. A working note
about a running task expires in hours. What became of a task is kept for months
and fades in the ranking as it ages. What you said you want - "always Markdown",
"never touch the originals" - does not expire at all, because a preference is
superseded by another preference, not by time.

Who may read what is not a filter a caller remembers to pass. An employee sees
this workspace's memory, the memory of the plan it is working inside, and its own
private notes - never another employee's. That is enforced where the rows are,
and every search in the platform goes through one method, so replacing the local
full-text index with something else later is replacing one file. See
[ADR 0009](docs/adr/0009-memory-is-reached-only-through-recall.md).

Memory can be switched off entirely (`PROMETHEUS_FLAGS__MEMORY=false`), and then the
platform behaves exactly as it did before it had one.

## Tools, and the brake on them

An employee gets the tools its declaration lists and nothing else - `prometheus tools`
prints the grants, so least privilege is something you can read rather than
trust. The filesystem tools see one directory (`PROMETHEUS_WORKSPACE_DIR`, by default
`~/.prometheus/workspace`) and refuse any path that resolves outside it,
symlinks followed.

An action at HIGH or CRITICAL risk waits for a person, and how risky an action is
follows from **what it does to the world** rather than from a number somebody
typed on the tool. Reading is low, writing is medium, and sending, spending,
deleting, publishing and running generated code are high. A tool may declare
itself riskier than its effect implies - a read of something sensitive is a real
case - and cannot declare itself safer.

```bash
uv run prometheus policies            # the table, the named rules, and who opted in
uv run prometheus approvals           # what is waiting on a decision
uv run prometheus approve <id>        # or: prometheus reject <id> --comment "not that file"
uv run prometheus audit               # what was done here, including what was refused
```

On top of that floor, an employee's declaration can **narrow** and never widen.
`policies: [read_only]` refuses a write outright rather than asking about it,
because a declared restriction is not a question; `no_sending`, `no_spending`,
`no_deleting` and `no_publishing` do the same for their own verb. A policy name
nothing answers to fails the declaration, since a typo would otherwise read in
the file as a restriction that is in force. See
[ADR 0010](docs/adr/0010-risk-follows-the-effect-and-a-declaration-only-narrows.md)
and [ADR 0004](docs/adr/0004-approval-is-a-risk-level-not-a-list-of-actions.md).

With nobody at the terminal the answer is no, so an unattended run cannot
consent by being silent - set `PROMETHEUS_APPROVAL_MODE=allow` if that is what you
want on your own machine, or set `PROMETHEUS_SECRET_TELEGRAM_BOT_TOKEN` and
`PROMETHEUS_SECRET_TELEGRAM_CHAT_ID` and be asked wherever you actually are.

Under `prometheus serve` the same question appears in the page and the run really is
parked on it - the task shows as WAITING_FOR_APPROVAL until you answer. A
question nobody answers expires, and an expired question is a no.

`prometheus audit` is the list that includes what did *not* happen. A refused action
leaves no tool call, because the tool never ran, so it is recorded there or
nowhere.

The browser is an optional extra, so installing the platform does not download a
browser engine for a workforce that only reads files:

```bash
uv sync --extra browser && uv run playwright install chromium
```

## Operating a screen

Some interfaces have no API and nothing to address by structure - a canvas, an
embedded viewer, a control that only answers to a mouse. For those there is a
screen, and one rule around it: **use the most direct way in that exists.**

```
API  ->  integration  ->  browser  ->  Computer Use  ->  desktop
```

That order is not advice in a prompt. Every tool declares which rung it is on,
`prometheus tools` prints it, the choice is logged before the first step, and each call
is stored with the level it went through - so a run that clicked on a picture of
a button can be asked why afterwards. See
[ADR 0005](docs/adr/0005-the-interface-hierarchy-is-a-property-of-the-tool.md).

The loop the tools are built for is **look, act, check**. `computer.screen`
shows the screenshot to a vision model and answers with coordinates - the only
place a click may get one. Every action takes an optional `expect` and confirms
it by looking again, so the result reports what the screen showed rather than
that the click was issued.

```bash
uv run prometheus run-task --employee operator "Open file:///.../keypad.html and enter the code 4 7 2, then press OK."
uv run prometheus stop --reason "wrong window"   # from any terminal, at any moment
uv run prometheus stop --clear
```

`prometheus stop` writes a file that every action on a screen reads before it happens,
so it works from a second terminal while the run has the screen, and a stop set
while nothing is running still holds when the next one starts.

### The desktop

Driving the page the platform opened comes with the browser tools. Driving *your
machine* is separate, off by default, and confined:

```bash
uv sync --extra desktop
export PROMETHEUS_FLAGS__COMPUTER_USE=true
export PROMETHEUS_COMPUTER_ALLOWED_APPLICATIONS='["Preview"]'
export PROMETHEUS_COMPUTER_ALLOWED_REGION=1440x820+0+80
```

An empty application list means the desktop is off limits entirely - acting on
the machine is opt-in per application, the way files are opt-in per directory -
and "the platform could not tell what is in front" is a refusal, not a shrug.
Every desktop action also waits for you: `desktop.*` tools are irreversible by
declaration, so the gate asks each time.

With computer use off, every scenario that has an API or a browser path keeps
working. They are different rungs of the same ladder, not the same tool with a
switch.

### Adding a tool

One file under `infrastructure/tools/` and one line in
`infrastructure/tools/builtin.py`. Declare the parameters and the JSON Schema
the model sees is generated from them; declare the risk and the gate applies it.
Nothing in the runtime changes.

### Without a key, and without spending anything

A model running on this machine works just as well, and is what Phase 2 was
validated against:

```bash
ollama serve && ollama pull gpt-oss:20b
export PROMETHEUS_MODEL_CATALOG_PATH=infrastructure/llm/models.local.toml
uv run prometheus ask "Which city is the capital of Germany?"
```

That is the same code path - router, adapter, metering, spend log - pointed at a
different catalog. Local calls are priced at zero because they are.

## Connecting something outside this machine

Prometheus can reach services it did not ship with. In the window, Settings →
Integrations takes a name and a command - any MCP server, nothing about it baked
in - starts it, and shows what it turned out to offer:

```
notes  ready, 3 capability(ies)
  offers EMAIL
     search_notes            READ    LOW
   ! send_note               EXECUTE HIGH  (unclassified)
   ! unclassified_thing      EXECUTE HIGH  (unclassified)
  granted to nobody

  ! waits for you before it runs.
```

`prometheus integrations` prints the same thing in a terminal.

Three things about that listing are the whole design.

**What each capability does to the world is decided here, not by the server.** A
server that described its own "send" as harmless would otherwise walk past the
approval gate, so its claims are a suggestion and the stored classification is
yours. Anything nobody has classified is treated as the most dangerous thing it
could be, which is why two of the three above wait for you.

**Nobody can use it until you say who.** Connecting a service does not hand it to
every employee. An employee is granted the integration by name -
`integrations: [notes]` in its declaration, or a click in the window - and gets
whatever that service offers now, including whatever it offers after an update.

**What comes back is quoted, not obeyed.** A mail body or an issue is text
written by someone who is not you. It reaches the model inside markers that say
so, and nothing inside it can change a policy, a permission or a credential.

Disabling a service keeps its setup and its credentials; removing it takes its
capabilities away and leaves every record of what it already did. Credentials go
in and are never read back out - there is no endpoint that returns one.

## Running something you already know the shape of

A workflow is a file under `workflows/`: named steps, who does each, and what
each depends on. Adding one requires no change to any employee and no Python at
all.

```bash
uv run prometheus workflows                                  # what is declared, and can it run
uv run prometheus run-workflow inbox-triage
uv run prometheus run-workflow weekly-report --input folder=sales
```

```yaml
name: weekly-report
steps:
  - name: survey
    employee: organizer
    instruction: List everything under {folder} and say what is there.
  - name: numbers
    employee: analyst
    depends_on: [survey]
    instruction: Compute what these files support. The survey said {steps.survey}
    max_attempts: 2          # reading and computing again costs nothing
```

Dependencies are declared edges, so a cycle is reported rather than looped on,
and a step reads what earlier steps produced through `{steps.<name>}`. A failed
step stops the run by default - the step after it usually reads what it produced
- and `on_failure: CONTINUE` says otherwise for a step whose output is a
nice-to-have. Retry lives on the step because whether repeating is safe depends
on what the step does.

Everything below the decomposition is the same as for work Prometheus planned
itself: the same employees, the same limits, the same approval gate.

## Adding an employee

Create `employees/<name>/employee.yaml`. That is the whole change - no class, no
registration, no edit to the runtime:

```yaml
name: translator
role: Translator
goals:
  - text: Say what the original says, not what it would have said.
allowed_tools: [fs.read, fs.write]   # may it?  least privilege
capabilities: [FILE_ACCESS]          # can it?  what Prometheus searches by
model_profile:
  capabilities: [TEXT_REASONING, LONG_CONTEXT]
limits:
  max_steps: 8
  max_cost_usd: 0.50
```

The two lists answer different questions, and a single one would silently answer
one of them wrong. `allowed_tools` is what it may reach; `capabilities` is what
work it can be given. Leave a capability out and that work never arrives; claim
one with no tool behind it and the work arrives and cannot be started.

```bash
uv run prometheus employees            # both lists, plus what disagrees with this machine
uv run prometheus employees --strict   # and exit non-zero if anything does
```

A declaration is checked when it loads - an unknown field, a temperature of 20,
a budget of zero - and named by file, because the alternative is an employee
that quietly has no tools.

An optional `prompts/system.md` next to it gives the employee its own voice.
All employees share one runtime; a second runtime would mean the difference
between two employees had stopped being declarative. Prometheus finds it on the next
run - nothing in the manager names an employee, and a test proves it by reading
this directory.

## Changing models

Edit `infrastructure/llm/models.toml`. Nothing in `domain/`, `application/` or an
employee declaration names a model or a vendor, so that file is the whole change.

Two catalogs ship. The default reaches models through OpenRouter - one key for
many vendors. `models.anthropic.toml` talks to Anthropic directly:

```bash
export PROMETHEUS_MODEL_CATALOG_PATH=infrastructure/llm/models.anthropic.toml
# PROMETHEUS_LLM_API_KEY=sk-ant-... in .env
```

A caller asks for what the work *needs* - reasoning, tool calling, a long
context - and the router answers from the catalog. Precedence is: requirements
filter the field, the configured default for that kind of work wins, hints rank
whatever is left. See [ADR 0003](docs/adr/0003-the-configured-default-model-wins.md).

Prompts are files, versioned by the directory they sit in: `prompts/<name>/v1.md`,
with `v2.md` next to it when the wording changes rather than replacing it.

```bash
uv run prometheus prompts             # name, current version, and a digest of the text
```

The digest is the part worth having. A version number says which file a run
used; the hash says whether that file is still the text it was, which is the
difference between two runs being comparable and merely looking it.

## Layout

| Directory | Layer | Rule |
|---|---|---|
| `app/` | Transport | The CLI and the HTTP adapter. The composition root lives here. |
| `application/` | Coordination | Orchestration, the one shared employee runtime, and `interface/` - the boundary every surface talks to. Depends on `domain/` only. |
| `domain/` | Business logic | Protocols and values. Depends on nothing. |
| `infrastructure/` | Adapters | Providers, persistence, tools. Depends on `domain/` only. |
| `employees/` | Declarations | An employee is a definition file, not code. |
| `prompts/` | Content | Planner and verifier templates, versioned as files. |
| `workflows/` | Declarations | A predefined process is a file, not code. |
| `desktop/` | Interface | The Tauri + React window. An adapter over `application/interface/`, with no business logic of its own. |

The import rules are enforced by `import-linter` and by
`tests/unit/test_architecture_boundaries.py`. An `httpx` import inside `domain/`
fails CI.

## Development

```bash
uv run pytest                        # no network, no provider keys needed
uv run ruff check .
uv run lint-imports
uv run python scripts/check_english_only.py

cd desktop && npm test               # the window, against a scripted runtime
```

`tests/integration/test_local_provider.py` is the one exception to "no network":
it talks to a model on this machine when one is running, and skips itself when
one is not. Nothing in the suite ever needs a key or a paid call.

The codebase is English-only - identifiers, comments, logs, schema and docs. Task
goals, memory contents and report text are runtime data and may be in any
language; the language agents answer in is the `PROMETHEUS_RESPONSE_LANGUAGE` setting.
