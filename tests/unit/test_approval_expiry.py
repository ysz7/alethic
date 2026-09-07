"""A question with a deadline (Phase 10, §10.4).

The reason this exists is not tidiness. A PENDING row is a task `alethic resume`
keeps picking up, so a question nobody ever answers is a run that never
finishes - and the answer to "nobody was there" has to be the same as the answer
to "they said no".
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from domain.approvals.models import Approval, ApprovalRequest, ApprovalState
from infrastructure.approvals.service import ApprovalMode, LocalApprovalService
from infrastructure.persistence.approval_repository import InMemoryApprovalRepository


def request(**extra) -> ApprovalRequest:
    return ApprovalRequest.create(task_id=uuid4(), action="fs.write(path='x')", **extra)


# --- The value ----------------------------------------------------------------


def test_a_question_with_no_deadline_never_goes_overdue():
    """The terminal case: somebody is standing there, so waiting is correct."""
    assert Approval(request=request()).is_overdue() is False


def test_a_question_past_its_deadline_is_overdue():
    old = request().expiring_in(60)
    later = old.requested_at + timedelta(seconds=61)
    assert Approval(request=old).is_overdue(later) is True


def test_an_answered_question_is_never_overdue():
    """Expiry is about unanswered questions. A decision already made stands."""
    old = request().expiring_in(60)
    answered = Approval(request=old).resolve(ApprovalState.APPROVED)
    assert answered.is_overdue(old.requested_at + timedelta(days=1)) is False


def test_expiring_in_nothing_leaves_the_question_open():
    for value in (0, -5, None):
        assert request().expiring_in(value).expires_at is None


# --- The store ----------------------------------------------------------------


async def test_overdue_questions_are_closed_where_they_are_stored():
    """The process that asked is gone by the time the deadline passes, so
    nothing is holding the request in memory to time out. The row is all there
    is, and closing it is what this does."""
    repository = InMemoryApprovalRepository()
    overdue = request().expiring_in(1)
    await repository.save(Approval(request=overdue))
    await repository.save(Approval(request=request()))

    closed = await repository.expire_overdue(datetime.now(UTC) + timedelta(minutes=5))

    assert closed == 1
    stored = await repository.get(overdue.id)
    assert stored is not None and stored.state is ApprovalState.EXPIRED
    assert stored.resolved_by == "timeout"


async def test_listing_what_is_pending_does_not_show_what_has_expired():
    repository = InMemoryApprovalRepository()
    await repository.save(Approval(request=request().expiring_in(0.001)))
    await asyncio.sleep(0.01)

    assert await repository.list_pending() == []


# --- The service --------------------------------------------------------------


async def test_a_confirmer_that_never_answers_expires_rather_than_waiting_forever():
    async def never() -> bool:
        await asyncio.Event().wait()
        return True

    service = LocalApprovalService(
        InMemoryApprovalRepository(),
        mode=ApprovalMode.PROMPT,
        confirmer=lambda _: never(),
        ttl_seconds=0.01,
        is_interactive=lambda: True,
    )

    assert await service.request(request()) is ApprovalState.EXPIRED


async def test_an_expired_question_is_stored_as_expired():
    repository = InMemoryApprovalRepository()

    async def never() -> bool:
        await asyncio.Event().wait()
        return True

    service = LocalApprovalService(
        repository,
        mode=ApprovalMode.PROMPT,
        confirmer=lambda _: never(),
        ttl_seconds=0.01,
        is_interactive=lambda: True,
    )
    asked = request()
    await service.request(asked)

    stored = await repository.get(asked.id)
    assert stored is not None and stored.state is ApprovalState.EXPIRED


async def test_a_terminal_prompt_is_never_timed_out_from_under_the_person():
    """A synchronous confirmer is somebody at a keyboard. Stealing the prompt
    while they read it would be worse than waiting."""
    service = LocalApprovalService(
        InMemoryApprovalRepository(),
        mode=ApprovalMode.PROMPT,
        confirmer=lambda _: True,
        ttl_seconds=0.001,
        is_interactive=lambda: True,
    )

    assert await service.request(request()) is ApprovalState.APPROVED
