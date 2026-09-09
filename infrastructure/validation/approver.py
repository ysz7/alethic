"""The person a scenario says would have been there.

Every approval recorded by the first full validation pass was rejected by
`no-approver`: the suite runs with nothing attached to stdin, so every action
above the threshold was refused and three scenarios whose work begins with
writing a file could not pass on any model. The report then blamed approvals for
runs whose real problem was never reached.

Configuring the machine to allow was the obvious answer and the wrong one. It is
machine-wide, so it would also allow the scenario whose entire point is that the
platform refuses, and it would record a suite in which the brake was switched
off - which measures a different product.

So the answer is declared per scenario, per tool, and applies for exactly one
run. Anything not named is refused, because a suite where silence means yes is a
suite that stops noticing when the gate breaks.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from domain.approvals.models import ApprovalRequest
from infrastructure.observability.logging import get_logger

log = get_logger(__name__)


class DeclaredApprover:
    """Implements `domain.validation.protocols.Approver`."""

    def __init__(self) -> None:
        self._allowed: frozenset[str] = frozenset()

    def confirm(self, request: ApprovalRequest) -> bool:
        """Answer by tool name, never by reading the rendered action line."""
        answer = request.tool in self._allowed
        log.info(
            "validation.approval_answered",
            tool=request.tool,
            action=request.action[:80],
            approved=answer,
        )
        return answer

    @contextmanager
    def answering(self, allowed: frozenset[str]) -> Iterator[None]:
        previous = self._allowed
        self._allowed = allowed
        try:
            yield
        finally:
            self._allowed = previous
