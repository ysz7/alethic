"""The HTTP adapter: transport, and deliberately nothing else.

Phase 6's Definition of Done is that a developer uses Alethic without reading logs
in a terminal. Phase 7 changed what the page asks for - an outcome, not an
employee. Phase 13 changed where the answer comes from: every route here now
calls `AlethicService`, the application-level boundary, and this file owns URLs,
status codes, request bodies and the framing of an event stream. That is the
whole of its job. A rule that lives here is a rule the desktop shell and a chat
bot would each have to reimplement, and the three would disagree.

**It binds to 127.0.0.1 and has no authentication.** Those two facts are one
decision, not two. The interface starts tasks, approves irreversible actions and
can stop the machine's screen; it is safe without a password precisely because
nothing off this machine can reach it. Binding it anywhere else would turn a
local tool into an unauthenticated remote one, which is why the host is a
setting that documents itself rather than a command-line flag inviting `0.0.0.0`.

**The trace is pushed, not polled.** Server-sent events, because the traffic is
one-way - the server describes, the client draws - and SSE reconnects on its
own, needs no library, and survives a window being left open while nothing runs.
A websocket would buy a direction nobody uses.

**Approvals are answered here, and the run really is parked.** The tool call
waits on a future (`WaitingConfirmer`); this hands it the answer. Nothing is
approved by default, by timeout, or by the page being closed.

**The desktop shell is a client of this, not a second server.** It talks the
same HTTP and the same SSE a browser does, which is what keeps it an interface
rather than a fork of the platform - and what makes the browser page and the
Tauri window two views of one running engine rather than two engines.

The container, the runner and the live runs are per-application, created at
startup and closed at shutdown, so a client talking to a dead engine is not a
state this can be in.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config.container import build_container, build_manager, build_service
from app.config.settings import Settings, get_settings
from application.interface.activity import ActivityEvent
from application.interface.contracts import InputType, RequestSource, UserRequest
from application.interface.service import AlethicService, ApprovalsDisabledError
from application.scheduling.scheduler import Scheduler
from domain.errors import AlethicError, StorageNotInitializedError
from infrastructure.approvals.waiting import WaitingConfirmer
from infrastructure.container import Container

log = structlog.get_logger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

#: How long the event stream waits before sending a comment line. Without it a
#: proxy or a sleeping laptop can drop an idle connection with nothing to show
#: for it, and the client would sit silently on a stream that is already dead.
HEARTBEAT = ": keep-alive\n\n"

#: The origins a desktop shell talks from. Two kinds, and the second one was
#: learned the hard way: in development the window loads from a local dev
#: server, but a *packaged* window serves its page from Tauri's own protocol
#: and sends `tauri://localhost` as its origin - so a list of loopback URLs
#: silently blocks every built application while every development run works.
#:
#: They are still all local: a custom protocol on this machine and two loopback
#: ports. Nothing here widens what can reach this server from a network.
DESKTOP_ORIGINS = (
    "tauri://localhost",
    "http://tauri.localhost",
    "http://localhost:1420",
    "http://127.0.0.1:1420",
)


class NewTask(BaseModel):
    goal: str = Field(min_length=1)
    employee: str = Field(min_length=1)


class NewObjective(BaseModel):
    request: str = Field(min_length=1)
    conversation_id: UUID | None = None
    #: Which interface this arrived from, and what the person actually gave.
    #: Recorded on the way in and never branched on; see
    #: `application/interface/contracts.py`.
    source: RequestSource = RequestSource.WEB
    input_type: InputType = InputType.TEXT


class NewConversation(BaseModel):
    title: str = ""


class Decision(BaseModel):
    approved: bool
    comment: str = ""


class Cancellation(BaseModel):
    reason: str = ""


def create_app(
    settings: Settings | None = None,
    *,
    build: Callable[[Settings], Container] = build_container,
) -> FastAPI:
    """Build the interface around its own container.

    Settings and the way the container is built are both arguments, for the same
    reason the container is handed its settings rather than reading them: it is
    what lets the whole interface be exercised against a temporary database and
    a scripted model, with no server running and no provider key configured.
    """
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = build(resolved)
        # Set before anything can ask: an approval that reached stdin while the
        # person is looking at a window is an approval nobody can answer.
        confirmer = WaitingConfirmer(
            timeout_seconds=resolved.ui_approval_timeout_seconds,
            progress=container.progress,
        )
        container.use_approval_confirmer(confirmer)
        await container.sync_employees()

        app.state.settings = resolved
        app.state.container = container
        app.state.confirmer = confirmer
        app.state.service = build_service(
            container, confirmer, history_limit=resolved.ui_history_limit
        )
        # Started on the same loop that serves the requests, for the same
        # reason a task is: one process, one database, and a proactive
        # objective that is watched in the trace exactly like one somebody
        # asked for. Off unless the flag says otherwise - work nobody asked
        # for is opt-in.
        stop_scheduler = asyncio.Event()
        scheduler_task: asyncio.Task[None] | None = None
        if resolved.scheduler_enabled:
            scheduler = Scheduler(
                manager=build_manager(container),
                schedules=container.schedule_repository,
                events=container.event_log,
                tick_seconds=resolved.scheduler_tick_seconds,
            )
            scheduler_task = asyncio.create_task(scheduler.run_forever(stop_scheduler))

        log.info(
            "ui.started",
            host=resolved.ui_host,
            port=resolved.ui_port,
            scheduler=resolved.scheduler_enabled,
        )
        try:
            yield
        finally:
            stop_scheduler.set()
            if scheduler_task is not None:
                # Awaited rather than cancelled: a firing that is halfway
                # through an objective should finish the tick it is in, and the
                # loop already checks the signal between them.
                await scheduler_task
            await app.state.service.aclose()
            await container.aclose()

    app = FastAPI(title="Alethic", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(DESKTOP_ORIGINS),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _routes(app)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


# --- Routes -------------------------------------------------------------------


def _routes(app: FastAPI) -> None:
    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health(request: Request) -> dict[str, Any]:
        """Is the engine answering. What a shell polls while it starts one up."""
        return _service(request).health()

    @app.get("/api/employees")
    async def employees(request: Request) -> dict[str, Any]:
        return {"employees": _service(request).list_employees()}

    @app.get("/api/tasks")
    async def history(request: Request) -> dict[str, Any]:
        return {"tasks": await _guarded(_service(request).list_tasks())}

    @app.post("/api/tasks", status_code=201)
    async def start(request: Request, body: NewTask) -> dict[str, Any]:
        try:
            return await _service(request).start_task(body.goal, body.employee)
        except AlethicError as error:
            # An unknown employee is the user asking for something that does not
            # exist, not a server fault: 400, with the reason said plainly.
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/tasks/{task_id}")
    async def detail(request: Request, task_id: UUID) -> dict[str, Any]:
        found = await _guarded(_service(request).get_task(task_id))
        return _found(found, f"Unknown task: {task_id}")

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel(request: Request, task_id: UUID, body: Cancellation) -> dict[str, Any]:
        found = await _guarded(_service(request).cancel_task(task_id, body.reason))
        return _found(found, f"Unknown task: {task_id}")

    # --- Conversations --------------------------------------------------------

    @app.post("/api/conversations", status_code=201)
    async def open_thread(request: Request, body: NewConversation) -> dict[str, Any]:
        return await _guarded(_service(request).create_conversation(body.title))

    @app.get("/api/conversations")
    async def threads(request: Request) -> dict[str, Any]:
        return {"conversations": await _guarded(_service(request).list_conversations())}

    @app.get("/api/conversations/{conversation_id}")
    async def thread(request: Request, conversation_id: UUID) -> dict[str, Any]:
        found = await _guarded(_service(request).get_conversation(conversation_id))
        return _found(found, f"Unknown conversation: {conversation_id}")

    @app.post("/api/conversations/{conversation_id}/messages", status_code=201)
    async def say(
        request: Request, conversation_id: UUID, body: NewObjective
    ) -> dict[str, Any]:
        """Say something in a thread. One message is one objective."""
        return await _ask(request, body, conversation_id=conversation_id)

    # --- The manager ----------------------------------------------------------

    @app.post("/api/objectives", status_code=201)
    async def ask(request: Request, body: NewObjective) -> dict[str, Any]:
        """State a goal. Alethic decides what it means and who does it."""
        return await _ask(request, body, conversation_id=body.conversation_id)

    @app.get("/api/objectives")
    async def objectives(request: Request) -> dict[str, Any]:
        return {"objectives": await _guarded(_service(request).list_objectives())}

    @app.get("/api/objectives/{objective_id}")
    async def objective(request: Request, objective_id: UUID) -> dict[str, Any]:
        found = await _guarded(_service(request).get_objective(objective_id))
        return _found(found, f"Unknown objective: {objective_id}")

    @app.post("/api/objectives/{objective_id}/cancel")
    async def stop_objective(request: Request, objective_id: UUID) -> dict[str, Any]:
        found = await _guarded(_service(request).cancel_objective(objective_id))
        return _found(found, f"Unknown objective: {objective_id}")

    @app.get("/api/approvals")
    async def approvals(request: Request) -> dict[str, Any]:
        return {"approvals": await _guarded(_service(request).list_approvals())}

    @app.post("/api/approvals/{approval_id}")
    async def decide(request: Request, approval_id: UUID, body: Decision) -> dict[str, Any]:
        try:
            return await _service(request).decide_approval(
                approval_id, approved=body.approved, comment=body.comment
            )
        except ApprovalsDisabledError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except AlethicError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/spend")
    async def spend(request: Request) -> dict[str, Any]:
        return await _guarded(_service(request).spend())

    @app.get("/api/events")
    async def events(
        request: Request, task: UUID | None = None, objective: UUID | None = None
    ) -> StreamingResponse:
        service = _service(request)
        activity = (
            service.objective_activity(objective)
            if objective is not None
            else service.task_activity(task)
        )
        return StreamingResponse(
            _sse(request, activity),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


# --- The stream ---------------------------------------------------------------


async def _sse(
    request: Request, activity: AsyncIterator[ActivityEvent | None]
) -> AsyncIterator[str]:
    """Frame what the application layer is already saying.

    Everything about *what* is streamed - the replay, following an objective
    across its tasks, ending when the work does - belongs to `Activity`. What is
    left here is the wire format and the one thing only a transport knows: that
    a quiet connection needs a keep-alive, and that a client which has gone away
    should stop the iteration rather than be written to.
    """
    async for event in activity:
        if await request.is_disconnected():
            return
        yield HEARTBEAT if event is None else f"data: {json.dumps(event.to_dict())}\n\n"


# --- Helpers ------------------------------------------------------------------


def _service(request: Request) -> AlethicService:
    return request.app.state.service


def _found(value: dict[str, Any] | None, missing: str) -> dict[str, Any]:
    if value is None:
        raise HTTPException(status_code=404, detail=missing)
    return value


async def _ask(
    request: Request, body: NewObjective, *, conversation_id: UUID | None
) -> dict[str, Any]:
    try:
        return await _guarded(
            _service(request).submit(
                UserRequest(
                    content=body.request,
                    source=body.source,
                    input_type=body.input_type,
                    conversation_id=conversation_id,
                )
            )
        )
    except AlethicError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


async def _guarded(awaitable):
    """Turn "there is no schema yet" into an answer instead of a stack trace."""
    try:
        return await awaitable
    except StorageNotInitializedError as error:
        raise HTTPException(
            status_code=503,
            detail=f"{error} Run: uv run alembic upgrade head",
        ) from error
