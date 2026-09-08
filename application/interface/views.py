"""Domain values as JSON, in one place.

Kept apart from the routes so the shape the browser sees is defined once and can
be read without reading the server. It is a projection, not a serialization
format: the interface shows what a person needs to judge a run - what it did,
what it cost, what went wrong - and nothing that only the runtime cares about.

It sits in `application/` rather than in one interface's package because the
shape is a property of the platform, not of HTTP: a desktop shell, a page and a
chat bot showing three different summaries of the same run would be three
answers to a question with one answer.

Two omissions are deliberate. The transcript is not exposed: it is the model's
working memory, it is large, and a page that renders it becomes a log viewer,
which is exactly the thing Phase 6 exists to stop the developer reading. And
nothing here reaches into `execution.state`, so the interface does not become a
second consumer of the resume cursor's shape.
"""

from __future__ import annotations

from typing import Any

from domain.approvals.models import Approval, ApprovalRequest
from domain.conversations.models import Conversation
from domain.employees.definition import EmployeeDefinition
from domain.integrations.models import Integration
from domain.integrations.specs import spec_for
from domain.policies.risk import at_least
from domain.policies.rules import APPROVAL_THRESHOLD
from domain.tasks.task import Task, TaskEvent
from domain.tools.telemetry import ToolCallRecord
from domain.workforce.protocols import Objective, Plan


def task_summary(task: Task, *, running: bool = False) -> dict[str, Any]:
    """One line of history: enough to list, not enough to inspect."""
    return {
        "id": str(task.id),
        "goal": task.goal,
        "status": task.status.value,
        "running": running,
        "step": task.execution.step,
        "cost_usd": round(task.cost_usd, 6),
        "attempts": task.attempts,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "employee_id": str(task.assigned_employee_id) if task.assigned_employee_id else None,
    }


def task_detail(
    task: Task,
    *,
    running: bool = False,
    calls: list[ToolCallRecord] | None = None,
    events: list[TaskEvent] | None = None,
    employee: str | None = None,
) -> dict[str, Any]:
    """A past or present run, opened.

    The tool calls come from the stored log rather than the live stream, which
    is what makes an execution from last week open the same way as the one
    running now.
    """
    return {
        **task_summary(task, running=running),
        "employee": employee,
        "plan": task.plan.to_dict() if task.plan else None,
        "result": (
            {
                "summary": task.result.summary,
                "artifacts": list(task.result.artifacts),
            }
            if task.result
            else None
        ),
        "error": (
            {"kind": task.error.kind, "message": task.error.message} if task.error else None
        ),
        "calls": [tool_call(call) for call in calls or ()],
        "events": [
            {
                "from": event.from_status.value if event.from_status else None,
                "to": event.to_status.value,
                "at": event.created_at.isoformat(),
            }
            for event in events or ()
        ],
    }


def tool_call(call: ToolCallRecord) -> dict[str, Any]:
    """One action, as it was recorded - arguments already redacted on the way in."""
    return {
        "tool": call.tool,
        "success": call.success,
        "interface": call.interface.value,
        "latency_ms": call.latency_ms,
        "arguments": call.input_data,
        "output": call.output,
        "error": call.error,
        "at": call.created_at.isoformat(),
    }


def approval(request: ApprovalRequest, *, live: bool = True) -> dict[str, Any]:
    """A question waiting on a person.

    `live` says whether this process is the one parked on the answer. A PENDING
    row left behind by a killed run can still be recorded as decided, but no
    tool call is going to resume from it, and saying so beats implying it.
    """
    safe = request.redacted()
    return {
        "id": str(safe.id),
        "task_id": str(safe.task_id),
        "action": safe.action,
        "risk": safe.risk_level.value,
        "reason": safe.reason,
        "payload": safe.payload,
        "requested_at": safe.requested_at.isoformat(),
        "live": live,
    }


def stored_approval(record: Approval, *, live: bool = False) -> dict[str, Any]:
    return {**approval(record.request, live=live), "state": record.state.value}


def employee(definition: EmployeeDefinition) -> dict[str, Any]:
    return {
        "id": str(definition.id),
        "name": definition.name,
        "title": definition.role.title,
        "description": definition.role.description,
        "tools": sorted(definition.allowed_tools),
        "integrations": sorted(definition.integrations),
        "capabilities": sorted(str(c) for c in definition.capabilities),
        "limits": {
            "max_steps": definition.limits.max_steps,
            "max_cost_usd": definition.limits.max_cost_usd,
            "max_wall_time_seconds": definition.limits.max_wall_time_seconds,
        },
    }


# --- Integrations -------------------------------------------------------------


def integration_capability(item: Integration, tool) -> dict[str, Any]:
    """One thing an integration offers, with the platform's verdict attached.

    `requires_approval` is computed here and sent, rather than left for an
    interface to work out from the effect. An interface that decided which
    actions are dangerous would be a second policy engine - one written in
    TypeScript, disagreeing silently with the real one, and applied only on the
    surfaces that remembered to implement it. The rule is the same rule the
    gate applies, read from the same threshold.
    """
    spec = spec_for(item, tool)
    return {
        "name": tool.name,
        "qualified_name": spec.name,
        "description": tool.description,
        "effect": spec.effect.value,
        "risk": spec.risk_level.value,
        "requires_approval": at_least(spec.risk_level, APPROVAL_THRESHOLD),
        "classified": tool.name in item.effects,
    }


def integration(item: Integration) -> dict[str, Any]:
    """One connected service, as a person needs to see it.

    No credential and no part of one. `secrets` is the *names* of what it needs,
    because a person setting one up has to know which are missing, and a name is
    not a secret.
    """
    return {
        "id": str(item.id),
        "name": item.name,
        "kind": item.kind.value,
        "status": item.status.value,
        "enabled": item.enabled,
        "usable": item.is_usable,
        "capabilities": sorted(str(c) for c in item.granted_capabilities),
        "secrets": list(item.secret_names),
        "tool_count": len(item.discovered),
        "tools": [integration_capability(item, tool) for tool in item.discovered],
    }


# --- The manager --------------------------------------------------------------


def objective_summary(item: Objective, *, thinking: bool = False) -> dict[str, Any]:
    """One line of what has been asked for."""
    return {
        "id": str(item.id),
        "text": item.text,
        "status": item.status.value,
        "thinking": thinking,
        "created_at": item.created_at.isoformat(),
        "finished_at": item.finished_at.isoformat() if item.finished_at else None,
        "cost_usd": round(item.result.cost_usd, 6) if item.result else 0.0,
    }


def objective_detail(
    item: Objective, *, thinking: bool = False, plans: list[Plan] | None = None
) -> dict[str, Any]:
    """One request, opened: what Alethic made of it, and what it did about it.

    Every revision is shown, not only the last. A superseded plan is the only
    evidence of why a second attempt was needed, and hiding it would leave the
    user reading an answer with no account of how it was arrived at.
    """
    return {
        **objective_summary(item, thinking=thinking),
        "constraints": item.constraints,
        "acceptance_criteria": list(item.acceptance_criteria),
        "result": (
            {
                "summary": item.result.summary,
                "missing": list(item.result.missing),
                "output": item.result.output,
            }
            if item.result
            else None
        ),
        "plans": [plan_view(plan) for plan in plans or ()],
    }


def plan_view(plan: Plan) -> dict[str, Any]:
    return {
        "id": str(plan.id),
        "revision": plan.revision,
        "status": plan.status.value,
        "rationale": plan.rationale,
        "tasks": [
            {
                "id": str(task.id),
                "goal": task.goal,
                "status": task.status.value,
                "cost_usd": round(task.cost_usd, 6),
                "depends_on": [str(other) for other in sorted(plan.depends_on(task.id))],
            }
            for task in plan.tasks
        ],
    }


# --- Conversations ------------------------------------------------------------


def conversation(item: Conversation, *, messages: int = 0) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "messages": messages,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def message(item: Objective, *, thinking: bool = False) -> dict[str, Any]:
    """One turn of a conversation: what was asked, and what came back.

    A turn is an objective, so this is the objective summary plus the two things
    a chat view needs and a history list does not - the answer's text, and
    whether there is an answer yet. There is no separate message record; see
    `domain/conversations/models.py` for why one would be a second history of
    the same work.
    """
    answer = item.result
    return {
        **objective_summary(item, thinking=thinking),
        "answer": answer.summary if answer else "",
        "missing": list(answer.missing) if answer else [],
        "answered": answer is not None,
    }
