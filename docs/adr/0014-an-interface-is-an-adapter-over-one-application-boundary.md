# ADR 0014 - An interface is an adapter over one application boundary

**Status:** accepted (Phase 13)

## Context

Until Phase 13 the platform had two surfaces - the CLI and the local page - and
they did not overlap enough for the difference to hurt. `prometheus ask-prometheus`
awaits an objective in the foreground; the page could not, so `app/ui/runs.py`
grew the background carrier for objectives and tasks, `app/ui/views.py` grew the
projection of every domain value into JSON, and the route bodies grew the rest:
following an objective across the tasks it delegates, listing live approvals
beside stored ones, cancelling a run that this process is not running.

All of that is interface-agnostic, and all of it lived above the application
layer. A desktop shell, a Telegram adapter or an HTTP client written next would
have had to reimplement it or import a FastAPI module to get at it. The second
copy would drift, and the first surface written would quietly become the
reference implementation every other one imitates.

Phase 13 adds a desktop application, which is the moment that stops being
hypothetical.

## Decision

**One application-level boundary, and interfaces are adapters over it.**
`application/interface/` holds `UserRequest` (what comes in), `PrometheusService`
(the operations), `Activity` (what is happening), `Runs` (what this process is
carrying) and `views` (domain values as data). It imports `domain/` and the rest
of `application/`, like every other application module, and it knows nothing
about HTTP, SSE, a socket, a window or a process boundary.

`app/ui/` keeps URLs, status codes, request bodies and the framing of an event
stream, and nothing else. A rule that appears there is a rule the desktop shell
and a chat bot would each have to write again.

**The desktop shell is a client of the same local HTTP the page uses.** Tauri
owns a window and, on this machine, the lifetime of the runtime process; React
talks to `127.0.0.1` over the transport a browser already talks. There is no
second server, no IPC channel carrying domain objects, and no execution of any
kind in Rust or TypeScript.

**Where a request came from is recorded and never branched on.** `source` is on
`UserRequest` for the trace. The first `if request.source is DESKTOP` in the core
is the moment the platform acquires a favourite interface and every other one
becomes the degraded path, so the property is asserted in
`tests/e2e/test_the_desktop_interface.py`: the same sentence from two sources
produces the same objective, the same criteria and the same verdict.

**A conversation is a thread of objectives, not a second record.** One user
message is one objective - already carrying the verbatim request, the criteria,
the plans, the tasks and the answer. `conversations` is four columns and
`objectives.conversation_id` is a nullable label. See migration 012.

## Consequences

Adding an interface is writing an adapter: Telegram is a bot that builds a
`UserRequest` and renders `ActivityEvent`s, and the core does not change. The
CLI is unchanged and stays foreground, because a terminal genuinely wants to
wait.

Two things get harder, both deliberately. A route can no longer reach a
repository for one convenient field - the projection is extended in
`views`, where every interface gets it at once. And the boundary accumulates
methods as surfaces need them; the guard against it becoming a god object is
that every method is a short arrangement of existing components, and
`tests/unit/test_architecture_boundaries.py` fails the build if `app/ui/` starts
reaching past it.

The alternative rejected: letting the desktop shell talk to the runtime through
Tauri commands in Rust. It would have made the shell the only surface with a
private path into the platform, and the page a second-class client of its own
engine.
