"""Asking somebody who is not at the keyboard (Phase 10, §10.5).

No network: `httpx.MockTransport` answers the bot API. What is worth checking is
not the HTTP but the four ways this can go wrong, because every one of them has
to come out as "not approved" rather than as an exception or, worse, as a yes.
"""

from __future__ import annotations

import json
from uuid import uuid4

import httpx
import pytest

from domain.approvals.models import ApprovalRequest, ApprovalState
from domain.secrets.models import Secret
from infrastructure.approvals.telegram import TelegramApprovalService, format_request
from infrastructure.persistence.approval_repository import InMemoryApprovalRepository


class Secrets:
    """Implements `domain.secrets.protocols.SecretResolver`."""

    def __init__(self, **values: str) -> None:
        self._values = values

    def maybe(self, name: str) -> Secret | None:
        value = self._values.get(name)
        return Secret(name=name, _value=value) if value else None

    def get(self, name: str) -> Secret:
        secret = self.maybe(name)
        if secret is None:
            raise KeyError(name)
        return secret


CONFIGURED = Secrets(TELEGRAM_BOT_TOKEN="token", TELEGRAM_CHAT_ID="42")


def request(**extra) -> ApprovalRequest:
    return ApprovalRequest.create(
        task_id=uuid4(), action="bank.pay(amount=10)", reason="moves money", **extra
    )


def transport(*answers: object, sent: list[dict] | None = None) -> httpx.MockTransport:
    """A bot API that accepts the message and then replies with `answers`."""
    replies = list(answers)

    def handle(http_request: httpx.Request) -> httpx.Response:
        if http_request.url.path.endswith("/sendMessage"):
            if sent is not None:
                sent.append(json.loads(http_request.content or b"{}"))
            return httpx.Response(200, json={"ok": True, "result": {}})
        return httpx.Response(200, json={"ok": True, "result": replies.pop(0) if replies else []})

    return httpx.MockTransport(handle)


def service(mock: httpx.MockTransport, **extra) -> TelegramApprovalService:
    return TelegramApprovalService(
        InMemoryApprovalRepository(),
        CONFIGURED,
        client=httpx.AsyncClient(transport=mock),
        poll_seconds=0.01,
        **extra,
    )


def press(button: str, approval_id) -> list[dict]:
    return [{"update_id": 1, "callback_query": {"data": f"{button}:{approval_id}"}}]


# --- Configuration ------------------------------------------------------------


def test_a_machine_told_nothing_is_not_configured() -> None:
    assert TelegramApprovalService.configured(Secrets()) is False
    assert TelegramApprovalService.configured(Secrets(TELEGRAM_BOT_TOKEN="t")) is False
    assert TelegramApprovalService.configured(CONFIGURED) is True


# --- The message --------------------------------------------------------------


def test_the_message_carries_the_action_the_reason_and_the_risk() -> None:
    text = format_request(request())
    assert "bank.pay(amount=10)" in text
    assert "moves money" in text
    assert "HIGH" in text


async def test_what_is_sent_is_the_redacted_request() -> None:
    """It lands in a chat history, on a phone, on somebody else's servers."""
    sent: list[dict] = []
    asked = request(payload={"api_key": "sk-secret", "amount": 10})
    approvals = InMemoryApprovalRepository()
    telegram = TelegramApprovalService(
        approvals,
        CONFIGURED,
        client=httpx.AsyncClient(transport=transport(press("approve", asked.id), sent=sent)),
        poll_seconds=0.01,
    )

    await telegram.request(asked)

    assert "sk-secret" not in json.dumps(sent)
    stored = await approvals.get(asked.id)
    assert stored is not None and "sk-secret" not in json.dumps(stored.request.payload)


# --- The answer ---------------------------------------------------------------


async def test_pressing_approve_approves() -> None:
    asked = request()
    telegram = service(transport(press("approve", asked.id)))

    assert await telegram.request(asked) is ApprovalState.APPROVED


async def test_pressing_reject_rejects() -> None:
    asked = request()
    telegram = service(transport(press("reject", asked.id)))

    assert await telegram.request(asked) is ApprovalState.REJECTED


async def test_an_answer_to_a_different_question_is_not_taken_as_this_one() -> None:
    """The one bug an approval flow must not have."""
    asked = request()
    other = press("approve", uuid4())
    telegram = service(transport(other, press("reject", asked.id)))

    assert await telegram.request(asked) is ApprovalState.REJECTED


# --- Everything that can go wrong comes out as "not approved" -----------------


async def test_nobody_answering_expires_rather_than_waiting_forever() -> None:
    asked = request()
    telegram = service(transport([], [], []), ttl_seconds=0.02)

    assert await telegram.request(asked) is ApprovalState.EXPIRED


async def test_a_bot_api_that_is_unreachable_is_a_refusal() -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    telegram = service(httpx.MockTransport(broken))

    assert await telegram.request(request()) is ApprovalState.REJECTED


async def test_a_machine_that_was_never_configured_refuses_instead_of_raising() -> None:
    telegram = TelegramApprovalService(InMemoryApprovalRepository(), Secrets())

    assert await telegram.request(request()) is ApprovalState.REJECTED


async def test_the_decision_is_stored_whatever_it_was() -> None:
    approvals = InMemoryApprovalRepository()
    asked = request()
    telegram = TelegramApprovalService(
        approvals,
        CONFIGURED,
        client=httpx.AsyncClient(transport=transport(press("reject", asked.id))),
        poll_seconds=0.01,
    )

    await telegram.request(asked)

    stored = await approvals.get(asked.id)
    assert stored is not None
    assert stored.state is ApprovalState.REJECTED
    assert stored.resolved_by == "telegram"


async def test_resolving_something_that_does_not_exist_says_so() -> None:
    from domain.errors import NotFoundError

    telegram = TelegramApprovalService(InMemoryApprovalRepository(), CONFIGURED)

    with pytest.raises(NotFoundError):
        await telegram.resolve(uuid4(), ApprovalState.APPROVED)
