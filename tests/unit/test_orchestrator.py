"""Failure classification: what a failure means for what happens next."""

from __future__ import annotations

import pytest

from application.orchestrator import FailureKind, classify
from domain.errors import (
    ConfigurationError,
    EmployeeNotFoundError,
    IntegrationAuthenticationError,
    IntegrationProtocolError,
    IntegrationTimeoutError,
    IntegrationUnavailableError,
    InvalidRequestError,
    LimitExceededError,
    PermissionDeniedError,
    PlanningError,
    ProviderUnavailableError,
    RateLimitError,
    StorageNotInitializedError,
    TimeoutError,
)


@pytest.mark.parametrize(
    "error",
    [RateLimitError("slow down"), TimeoutError("too slow"), ProviderUnavailableError("down")],
)
def test_a_briefly_unavailable_world_is_worth_retrying(error) -> None:
    failure = classify(error)
    assert failure.kind is FailureKind.TRANSIENT
    assert failure.is_retryable


@pytest.mark.parametrize(
    "error",
    [
        InvalidRequestError("malformed schema"),
        PermissionDeniedError("not allowed"),
        EmployeeNotFoundError("nobody"),
    ],
)
def test_a_wrong_request_is_not_worth_retrying(error) -> None:
    failure = classify(error)
    assert failure.kind is FailureKind.PERMANENT
    assert not failure.is_retryable


def test_misconfiguration_needs_a_human_not_a_retry() -> None:
    assert classify(ConfigurationError("no API key")).kind is FailureKind.CONFIGURATION
    # An unreadable local database is the same kind of problem.
    assert classify(StorageNotInitializedError("no schema")).kind is FailureKind.CONFIGURATION


@pytest.mark.parametrize(
    "error", [PlanningError("no plan"), LimitExceededError("STEPS", "12 steps")]
)
def test_work_that_did_not_succeed_is_its_own_category(error) -> None:
    failure = classify(error)
    assert failure.kind is FailureKind.EXECUTION
    assert not failure.is_retryable


def test_an_unanticipated_error_is_treated_as_permanent_and_named() -> None:
    failure = classify(ZeroDivisionError("division by zero"))
    assert failure.kind is FailureKind.UNKNOWN
    assert failure.error_type == "ZeroDivisionError"
    assert not failure.is_retryable


def test_classification_reads_types_not_messages() -> None:
    # A retry decision that depends on the wording of an error message breaks
    # the first time a provider rewrites its copy.
    assert classify(RateLimitError("anything at all")).is_retryable
    assert not classify(InvalidRequestError("rate limit")).is_retryable


def test_an_unreachable_integration_is_worth_another_try_and_a_rejected_one_is_not() -> None:
    # Phase 14. The same question a provider failure answers, and deliberately
    # the same mechanism: a server that is not answering may answer next time,
    # while a credential the service rejected will keep being rejected until a
    # person changes it. Neither is decided by reading the message.
    assert classify(IntegrationUnavailableError("server is down")).is_retryable
    assert classify(IntegrationTimeoutError("no answer")).is_retryable
    assert not classify(IntegrationAuthenticationError("token revoked")).is_retryable
    assert not classify(IntegrationProtocolError("unreadable frame")).is_retryable
