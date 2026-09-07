"""SQLAlchemy models, written natively for SQLite.

UUIDs and timestamps are TEXT, JSON is TEXT read through SQLite's JSON
functions, and enums are TEXT with a CHECK constraint. Portability is provided
by the Protocols in `domain/`, not by a dialect-agnostic subset of SQL.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DDL,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from domain.approvals.models import ApprovalState
from domain.memory.models import MemoryKind, MemoryScope
from domain.policies.models import ActorKind
from domain.tasks.task import TaskStatus
from domain.workflows.definition import WorkflowTrigger
from domain.workforce.protocols import ObjectiveStatus, PlanStatus
from infrastructure.persistence import memory_fts

TASK_STATUS_VALUES = tuple(status.value for status in TaskStatus)
APPROVAL_STATE_VALUES = tuple(state.value for state in ApprovalState)
OBJECTIVE_STATUS_VALUES = tuple(status.value for status in ObjectiveStatus)
PLAN_STATUS_VALUES = tuple(status.value for status in PlanStatus)
MEMORY_SCOPE_VALUES = tuple(scope.value for scope in MemoryScope)
MEMORY_KIND_VALUES = tuple(kind.value for kind in MemoryKind)
ACTOR_KIND_VALUES = tuple(kind.value for kind in ActorKind)
AUDIT_RESULT_VALUES = ("SUCCESS", "FAILURE", "DENIED")
WORKFLOW_TRIGGER_VALUES = tuple(trigger.value for trigger in WorkflowTrigger)
WORKFLOW_STATUS_VALUES = ("RUNNING", "COMPLETED", "FAILED", "CANCELLED")


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EmployeeRow(Base):
    """The loaded version of an employee declaration.

    The source of truth stays the file under `employees/`; this table holds what
    was loaded plus any local override.
    """

    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_employees_workspace_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(256), nullable=False)
    role_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    goals: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    policies: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    allowed_tools: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    model_profile: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    memory_scope: Mapped[str] = mapped_column(
        String(32), nullable=False, default="EMPLOYEE_PRIVATE"
    )
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    definition_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "','".join(TASK_STATUS_VALUES) + "')",
            name="ck_tasks_status",
        ),
        Index("ix_tasks_workspace_status", "workspace_id", "status", "priority", "created_at"),
        Index("ix_tasks_parent_id", "parent_id"),
        Index("ix_tasks_plan_id", "plan_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
    )
    # No FK yet: plans arrive in Phase 7.
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TaskStatus.CREATED.value
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    assigned_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=True
    )
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    #: Step cursor and scratch state, saved after every step so a task survives
    #: a restart.
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class TaskEventRow(Base):
    __tablename__ = "task_events"
    __table_args__ = (Index("ix_task_events_task_id", "task_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class LLMCallRow(Base):
    """Telemetry for every model call.

    Recorded from the first call rather than added later: local development pays
    for each token, and a looping agent gets expensive before it gets wrong.
    """

    __tablename__ = "llm_calls"
    __table_args__ = (Index("ix_llm_calls_task_id", "task_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class TaskAssignmentRow(Base):
    """Who was asked to do what, and on whose authority.

    Kept separate from `tasks` because a task can be assigned more than once -
    reassigned after a failure, retried, or handed to a different employee - and
    the history of that is what makes a run legible afterwards.
    """

    __tablename__ = "task_assignments"
    __table_args__ = (
        Index("ix_task_assignments_task", "task_id", "assigned_at"),
        Index("ix_task_assignments_employee", "employee_id", "assigned_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=False
    )
    assigned_by: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: What the delegator deliberately passed down - not the whole conversation.
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    assigned_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class ToolCallRow(Base):
    """Every tool call, with its arguments redacted.

    Model calls have been accounted for since Phase 2; tools need the same
    treatment for the same reason. A failing loop does not announce itself - it
    just keeps calling, and this is where that becomes visible after the fact.
    """

    __tablename__ = "tool_calls"
    __table_args__ = (Index("ix_tool_calls_task_id", "task_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Which level of the interface hierarchy the call went through. Stored so
    #: "why did it drive a screen rather than call something" is answerable from
    #: the trace months later, without re-deriving it from a tool declaration
    #: that may since have changed.
    interface: Mapped[str] = mapped_column(String(16), nullable=False, default="API")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class ApprovalRow(Base):
    """A question put to a human, and the answer.

    Written before the answer arrives, so a process killed mid-question leaves a
    PENDING row rather than an action nobody can account for.
    """

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "state IN ('" + "','".join(APPROVAL_STATE_VALUES) + "')",
            name="ck_approvals_state",
        ),
        Index("ix_approvals_state", "state", "requested_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_employee_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("employees.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    #: When the question stops being worth answering. NULL waits forever.
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class ObjectiveRow(Base):
    """What the user asked Alethic for, and what became of it.

    The user's own sentence is `text` and is never rewritten. What Alethic read out
    of it - the constraints, what would count as done - is stored beside it, so
    a misreading stays visible next to the thing it misread.
    """

    __tablename__ = "objectives"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "','".join(OBJECTIVE_STATUS_VALUES) + "')",
            name="ck_objectives_status",
        ),
        Index("ix_objectives_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    acceptance_criteria: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


class PlanRow(Base):
    """One revision of Alethic's decomposition of an objective.

    Superseded plans are kept. What the manager thought on the first attempt is
    the only evidence of why a second was needed.
    """

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('" + "','".join(PLAN_STATUS_VALUES) + "')",
            name="ck_plans_status",
        ),
        UniqueConstraint("objective_id", "revision", name="uq_plans_objective_revision"),
        Index("ix_plans_objective", "objective_id", "revision"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    objective_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)


class PlanTaskDependencyRow(Base):
    """One edge: this task cannot start until that one is done.

    Edges rather than an ordered list, because an order is a claim nobody
    checked. Edges can be checked for a cycle, and they say which tasks could
    run at the same time - which is what Phase 12 needs and what a list loses.

    The task columns carry no foreign key. A plan is recorded when Alethic proposes
    it, and a task becomes a row when somebody is given it, so the edges legally
    precede both ends they point at. See migration 006.
    """

    __tablename__ = "plan_task_dependencies"

    plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True
    )
    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    depends_on: Mapped[str] = mapped_column(String(36), primary_key=True)


class MemoryItemRow(Base):
    """One thing worth remembering, and who is allowed to remember it.

    `scope` is an access boundary rather than a label, so it is stored beside
    the owner it names: an EMPLOYEE_PRIVATE row without an `employee_id` would
    be private to nobody. The text search over `content` is an FTS5 virtual
    table kept in step by triggers - see `memory_fts` - and it is reached only
    through the memory adapter, never from a caller.

    `employee_id` and `task_id` carry no foreign key. Memory is written *about*
    a task and outlives it: an employee taken out of `employees/` and a task
    deleted from history would otherwise take with them the record of what was
    learned from them, which is the one thing here worth keeping.
    """

    __tablename__ = "memory_items"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('" + "','".join(MEMORY_SCOPE_VALUES) + "')",
            name="ck_memory_items_scope",
        ),
        CheckConstraint(
            "kind IN ('" + "','".join(MEMORY_KIND_VALUES) + "')",
            name="ck_memory_items_kind",
        ),
        Index("ix_memory_items_scope", "workspace_id", "scope", "kind", "created_at"),
        Index("ix_memory_items_employee", "employee_id", "kind", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # `metadata` is taken on a declarative class, so the attribute is renamed
    # and the column keeps the name the schema declares.
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)


class AuditRow(Base):
    """One action, who took it and what came of it.

    Separate from `tool_calls` on purpose: that table answers "what did this run
    cost and how long did it take", and this one answers "who did what here".
    The two overlap for a successful tool call and diverge exactly where it
    matters - a denied action has an audit line and no tool call, because the
    tool never ran, and those are the lines an audit exists for.

    No foreign keys. An audit outlives what it describes; keying it to `tasks`
    would mean clearing history erases the record of what was done, which is the
    one thing a record must survive.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "actor_kind IN ('" + "','".join(ACTOR_KIND_VALUES) + "')",
            name="ck_audit_log_actor_kind",
        ),
        CheckConstraint(
            "result IN ('" + "','".join(AUDIT_RESULT_VALUES) + "')",
            name="ck_audit_log_result",
        ),
        Index("ix_audit_log_ts", "ts"),
        Index("ix_audit_log_task", "task_id", "ts"),
        Index("ix_audit_log_actor", "actor_kind", "actor_id", "ts"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    actor_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assignment_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[str] = mapped_column(String(16), nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class WorkflowRunRow(Base):
    """One execution of a predefined process."""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('" + "','".join(WORKFLOW_TRIGGER_VALUES) + "')",
            name="ck_workflow_runs_trigger",
        ),
        CheckConstraint(
            "status IN ('" + "','".join(WORKFLOW_STATUS_VALUES) + "')",
            name="ck_workflow_runs_status",
        ),
        Index("ix_workflow_runs_started", "workspace_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    workflow: Mapped[str] = mapped_column(String(64), nullable=False)
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)


# The search index is part of the schema, not of the adapter: a database built
# by `create_all` - which is what the test suite does - has to be searchable the
# same way the migrated one is, or the tests exercise a different backend than
# the product ships.
for _statement in memory_fts.CREATE:
    event.listen(
        Base.metadata,
        "after_create",
        DDL(_statement).execute_if(dialect="sqlite"),
    )
