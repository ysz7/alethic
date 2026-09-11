"""Actor doubles. The whole suite runs without a network call."""

from __future__ import annotations

from domain.policies.models import ActorKind, SimpleActor


def user(*tools: str) -> SimpleActor:
    return SimpleActor("user", ActorKind.USER, frozenset(tools))


def prometheus(*tools: str) -> SimpleActor:
    return SimpleActor("prometheus", ActorKind.PROMETHEUS, frozenset(tools))


def employee(employee_id: str, *tools: str) -> SimpleActor:
    return SimpleActor(employee_id, ActorKind.EMPLOYEE, frozenset(tools))
