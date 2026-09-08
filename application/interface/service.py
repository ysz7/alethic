"""One object every interface talks to.

`AlethicService` is a facade and is written to stay one. It decides nothing: it
does not plan, does not choose an employee, does not call a tool and does not
judge whether an action is allowed. Every method here is a short arrangement of
things that already exist - the manager, the task runner, the repositories, the
approval service - and the moment one of them starts containing a rule, that
rule has been moved out of the core and into the interface layer, which is the
regression this package exists to prevent.

Two consequences worth stating.

**There is one way to start work, and this is not a second one.** A request
becomes an objective through `AlethicManager`, exactly as `ask-alethic`, a workflow
step and a schedule firing do. A method here that ran a task itself would be a
second execution engine wearing a convenience name.

**Unknown means None, not an exception.** Asking for a conversation that does
not exist is a normal thing for an interface to do - a stale link, a window
reopened after a database was cleared - and the answer is "there is no such
thing", which every transport can render. Exceptions are kept for what actually
went wrong.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog

from application.interface import views
from application.interface.activity import Activity, ActivityEvent
from application.interface.contracts import RequestSource, UserRequest
from application.interface.runs import Runs
from domain.approvals.models import ApprovalState
from domain.approvals.protocols import (
    ApprovalRepository,
    ApprovalService,
    ApprovalWaiter,
)
from domain.conversations.models import Conversation
from domain.conversations.repository import ConversationRepository
from domain.employees.protocols import EmployeeRegistry
from domain.errors import AlethicError
from domain.llm.telemetry import LLMCallLog
from domain.tasks.repository import TaskRepository
from domain.tools.telemetry import ToolCallLog
from domain.workforce.repository import ObjectiveRepository, PlanRepository
from domain.workspace.models import DEFAULT_WORKSPACE_ID

log = structlog.get_logger(__name__)

#: How much history a listing returns when the caller does not say. An
#: interface showing a person their own machine wants a page of it, not all of
#: it; anything wanting all of it is a report, and reports read the store.
DEFAULT_LIMIT = 50


class ApprovalsDisabledError(AlethicError):
    """Asked to decide something on a configuration with no approvals at all."""


@dataclass(frozen=True, slots=True)
class ServiceDependencies:
    """Everything the facade arranges, handed in rather than reached for.

    A frozen bag rather than a dozen constructor arguments, and deliberately
    not the container: the container knows how to build an adapter, and nothing
    in the application layer is allowed to.
    """

    runs: Runs
    activity: Activity
    conversations: ConversationRepository
    objectives: ObjectiveRepository
    plans: PlanRepository
    tasks: TaskRepository
    employees: EmployeeRegistry
    approvals: ApprovalRepository
    waiter: ApprovalWaiter
    tool_calls: ToolCallLog
    llm_calls: LLMCallLog
    approval_service: ApprovalService | None = None
    history_limit: int = DEFAULT_LIMIT


class AlethicService:
    """The application-level operations an interface is allowed to perform."""

    def __init__(self, dependencies: ServiceDependencies) -> None:
        self._d = dependencies

    # --- Conversations --------------------------------------------------------

    async def create_conversation(self, title: str = "", *, workspace_id=None) -> dict[str, Any]:
        conversation = Conversation.create(
            title,
            **({"workspace_id": workspace_id} if workspace_id is not None else {}),
        )
        await self._d.conversations.save(conversation)
        log.info("interface.conversation_created", conversation_id=str(conversation.id))
        return views.conversation(conversation)

    async def list_conversations(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        found = await self._d.conversations.list_recent(
            limit=limit or self._d.history_limit
        )
        return [views.conversation(item) for item in found]

    async def get_conversation(self, conversation_id: UUID) -> dict[str, Any] | None:
        """A thread and everything said in it, oldest first.

        The messages are objectives. Nothing is stored twice, so a thread cannot
        show an answer that the record of the work disagrees with.
        """
        conversation = await self._d.conversations.get(conversation_id)
        if conversation is None:
            return None
        thread = await self._d.objectives.for_conversation(conversation_id)
        return {
            **views.conversation(conversation, messages=len(thread)),
            "messages": [
                views.message(item, thinking=self._d.runs.is_thinking(item.id))
                for item in thread
            ],
        }

    # --- Asking for work ------------------------------------------------------

    async def submit(self, request: UserRequest) -> dict[str, Any]:
        """The one way in. Everything else on this object reads or stops work.

        The request's `source` is logged and never branched on: a sentence typed
        into a desktop window and the same sentence sent from a terminal produce
        the same objective and the same plan. That is the property the whole
        interface layer exists to keep, and it is kept here by not writing the
        `if`.
        """
        text = request.text
        if not text:
            raise AlethicError("An empty request has nothing to work on.")

        conversation = await self._thread_for(request)
        objective = await self._d.runs.ask(
            text, conversation_id=conversation.id if conversation else None
        )
        log.info(
            "interface.request_submitted",
            objective_id=str(objective.id),
            source=request.source.value,
            input_type=request.input_type.value,
            attachments=len(request.attachments),
            conversation_id=str(conversation.id) if conversation else None,
        )
        return views.message(objective, thinking=True)

    async def _thread_for(self, request: UserRequest) -> Conversation | None:
        """Name the thread after its first request, and mark it spoken in.

        A request naming a thread that no longer exists is not an error: the
        work is what the person asked for, and losing it to a stale window id
        would be the interface deciding something. It becomes a standalone
        objective, exactly like one from the CLI.
        """
        if request.conversation_id is None:
            return None
        conversation = await self._d.conversations.get(request.conversation_id)
        if conversation is None:
            log.info(
                "interface.unknown_conversation", conversation_id=str(request.conversation_id)
            )
            return None
        updated = conversation.titled_from(request.text).touched(request.received_at)
        await self._d.conversations.save(updated)
        return updated

    async def start_task(self, goal: str, employee: str) -> dict[str, Any]:
        """Hand one task to one named employee, bypassing the manager.

        Kept because a script and a machine with no interface still need it, and
        deliberately not what a conversational surface calls: choosing who does
        the work is the manager's job, not the user's.
        """
        task = await self._d.runs.start(goal.strip(), employee)
        return views.task_summary(task, running=True)

    # --- Watching -------------------------------------------------------------

    async def list_objectives(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        found = await self._d.objectives.list_recent(limit=limit or self._d.history_limit)
        return [
            views.objective_summary(item, thinking=self._d.runs.is_thinking(item.id))
            for item in found
        ]

    async def get_objective(self, objective_id: UUID) -> dict[str, Any] | None:
        item = await self._d.objectives.get(objective_id)
        if item is None:
            return None
        return views.objective_detail(
            item,
            thinking=self._d.runs.is_thinking(objective_id),
            plans=await self._d.plans.for_objective(objective_id),
        )

    async def list_tasks(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        found = await self._d.tasks.list_recent(limit=limit or self._d.history_limit)
        return [
            views.task_summary(task, running=self._d.runs.is_running(task.id))
            for task in found
        ]

    async def get_task(self, task_id: UUID) -> dict[str, Any] | None:
        task = await self._d.tasks.get(task_id)
        if task is None:
            return None
        names = {d.id: d.name for d in self._d.employees.list()}
        return views.task_detail(
            task,
            running=self._d.runs.is_running(task_id),
            calls=await self._d.tool_calls.list_for_task(task_id),
            events=await self._d.tasks.events(task_id),
            employee=names.get(task.assigned_employee_id) if task.assigned_employee_id else None,
        )

    def task_activity(self, task_id: UUID | None = None) -> AsyncIterator[ActivityEvent | None]:
        return self._d.activity.for_task(task_id)

    def objective_activity(self, objective_id: UUID) -> AsyncIterator[ActivityEvent | None]:
        return self._d.activity.for_objective(objective_id)

    # --- Stopping -------------------------------------------------------------

    async def cancel_task(self, task_id: UUID, reason: str = "") -> dict[str, Any] | None:
        task = await self._d.runs.cancel(task_id, reason)
        if task is None:
            return None
        return views.task_summary(task, running=self._d.runs.is_running(task_id))

    async def cancel_objective(self, objective_id: UUID) -> dict[str, Any] | None:
        stopped = await self._d.runs.cancel_objective(objective_id)
        item = await self._d.objectives.get(objective_id)
        if item is None:
            return None
        return {**views.objective_summary(item), "stopped": stopped}

    # --- Approvals ------------------------------------------------------------

    async def list_approvals(self) -> list[dict[str, Any]]:
        """What is waiting, live first.

        The stored rows are read too, because a question left behind by a killed
        run is still an open decision - it is simply one no tool call is parked
        on, and saying which is which beats implying they are the same.
        """
        live = {item.id: item for item in self._d.waiter.pending()}
        stored = await self._d.approvals.list_pending()
        return [views.approval(item, live=True) for item in live.values()] + [
            views.stored_approval(record) for record in stored if record.id not in live
        ]

    async def decide_approval(
        self, approval_id: UUID, *, approved: bool, comment: str = ""
    ) -> dict[str, Any]:
        """Answer a question. The interface carries the answer and nothing else.

        Whether the action needed asking was decided by the policy engine before
        this was ever shown to anybody; whether it now happens is decided by the
        person. Nothing in the interface layer gets a vote, which is why there
        is no path here that resolves an approval on its own.
        """
        state = ApprovalState.APPROVED if approved else ApprovalState.REJECTED
        answered = self._d.waiter.decide(approval_id, approved)
        if not answered:
            service = self._d.approval_service
            if service is None:
                raise ApprovalsDisabledError(
                    "Approvals are switched off in this configuration."
                )
            await service.resolve(approval_id, state, comment=comment)
        return {"id": str(approval_id), "state": state.value, "live": answered}

    # --- The workforce --------------------------------------------------------

    def list_employees(self) -> list[dict[str, Any]]:
        """Who is available, and what each of them may do.

        Read from the registry every time rather than cached: an employee is a
        directory, and one added while the interface is open should appear in it.
        """
        return [views.employee(d) for d in self._d.employees.list()]

    async def spend(self) -> dict[str, Any]:
        summary = await self._d.llm_calls.total()
        return {
            "calls": summary.calls,
            "prompt_tokens": summary.prompt_tokens,
            "output_tokens": summary.output_tokens,
            "cost_usd": round(summary.cost_usd, 6),
        }

    async def aclose(self) -> None:
        """Stop carrying work, without leaving a run half-written.

        The interface shutting down is not the work being abandoned: every live
        run is asked to stop the cooperative way first, so it writes its own
        terminal state and `resume` can pick it up.
        """
        await self._d.runs.aclose()

    def health(self) -> dict[str, Any]:
        """Enough for a shell to know the runtime it started is up.

        Deliberately touches no storage: a desktop application polling this
        while the engine boots must not open a database connection per poll,
        and "is the process answering" is the question being asked.
        """
        return {
            "status": "ok",
            "workspace": str(DEFAULT_WORKSPACE_ID),
            "sources": [source.value for source in RequestSource],
        }
