from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from domain.policies.models import RiskLevel
from domain.secrets.models import redact
from domain.workspace.models import DEFAULT_WORKSPACE_ID, WorkspaceId


class ApprovalState(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class ApprovalRequest:
    """A human decision an irreversible action is waiting on.

    Only a human resolves these. Prometheus can ask; it can never approve its own work.
    """

    id: UUID
    task_id: UUID
    action: str
    #: The tool this question is about. `action` is that tool rendered with its
    #: arguments, for a person to read; this is what the question is *about*,
    #: for anything that has to decide by tool rather than by prose. Kept apart
    #: because reading the name back out of the rendered line is parsing our own
    #: formatting, which is the habit the rest of the platform refuses.
    tool: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.HIGH
    workspace_id: WorkspaceId = DEFAULT_WORKSPACE_ID
    requested_by_employee_id: UUID | None = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    #: Why this action needed asking, in the words shown to the person deciding.
    reason: str = ""
    #: When this question stops being worth answering. None means it waits
    #: forever, which is the right default for a terminal prompt and the wrong
    #: one for a page nobody has open.
    expires_at: datetime | None = None

    @classmethod
    def create(cls, task_id: UUID, action: str, **extra: Any) -> ApprovalRequest:
        return cls(id=uuid4(), task_id=task_id, action=action, **extra)

    def redacted(self) -> ApprovalRequest:
        """The form that is safe to show and to store."""
        return replace(self, payload=redact(self.payload))

    def expiring_in(self, seconds: float | None) -> ApprovalRequest:
        """The same question with a deadline on it. None leaves it open."""
        if seconds is None or seconds <= 0:
            return self
        return replace(self, expires_at=self.requested_at + timedelta(seconds=seconds))


@dataclass(frozen=True, slots=True)
class Approval:
    """A request plus what was decided about it.

    Kept as one persisted value rather than two tables: the question and the
    answer are read together every time, and a pending request is just one whose
    answer has not arrived.
    """

    request: ApprovalRequest
    state: ApprovalState = ApprovalState.PENDING
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    comment: str = ""

    @property
    def id(self) -> UUID:
        return self.request.id

    @property
    def is_pending(self) -> bool:
        return self.state is ApprovalState.PENDING

    def is_overdue(self, now: datetime | None = None) -> bool:
        """Still unanswered, and past the point where answering it means much.

        An expired question is not an approved one. The whole design says an
        action nobody confirmed does not happen, and a deadline passing is one
        more way of nobody confirming it.
        """
        if not self.is_pending or self.request.expires_at is None:
            return False
        return (now or datetime.now(UTC)) >= self.request.expires_at

    def expire(self, now: datetime | None = None) -> Approval:
        return replace(
            self,
            state=ApprovalState.EXPIRED,
            resolved_at=now or datetime.now(UTC),
            resolved_by="timeout",
        )

    def resolve(
        self, decision: ApprovalState, *, resolved_by: str = "user", comment: str = ""
    ) -> Approval:
        return replace(
            self,
            state=decision,
            resolved_at=datetime.now(UTC),
            resolved_by=resolved_by,
            comment=comment,
        )
