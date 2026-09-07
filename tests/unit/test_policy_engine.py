"""The policy layer, decided as data (Phase 10, §10.1-10.2).

The three properties worth protecting here are the ones a future change is most
likely to break by accident: that risk follows the effect rather than a number
somebody typed, that a declaration can only ever narrow, and that a wrong policy
name is loud instead of silently enforcing nothing.
"""

from __future__ import annotations

import pytest

from domain.employees.definition import EmployeeDefinition, Role
from domain.employees.validation import Severity, check
from domain.policies.engine import PolicyRequest
from domain.policies.models import ActorKind, Decision, RiskLevel, SimpleActor
from domain.policies.risk import EFFECT_RISK, Effect, risk_of
from domain.policies.rules import APPROVAL_THRESHOLD, CATALOG, RuleBasedPolicyEngine
from domain.tools.models import ToolSpec

ENGINE = RuleBasedPolicyEngine()
ACTOR = SimpleActor("worker", ActorKind.EMPLOYEE, frozenset({"fs.write"}))


def ask(effect: Effect = Effect.READ, *, policies: frozenset[str] = frozenset(), **extra):
    return ENGINE.evaluate(
        PolicyRequest(
            actor=ACTOR,
            action="fs.write(path='notes.md')",
            tool="fs.write",
            effect=effect,
            risk_level=extra.pop("risk_level", risk_of(effect)),
            policies=policies,
            **extra,
        )
    )


# --- Risk follows the effect (§70, 10.2) --------------------------------------


def test_reading_is_low_and_the_four_dangerous_verbs_are_high():
    """§70 as a table. Named individually because the list is the rule."""
    assert EFFECT_RISK[Effect.READ] is RiskLevel.LOW
    assert EFFECT_RISK[Effect.WRITE] is RiskLevel.MEDIUM
    for effect in (Effect.SEND, Effect.SPEND, Effect.DELETE, Effect.PUBLISH):
        assert EFFECT_RISK[effect] is RiskLevel.HIGH


def test_a_spec_cannot_declare_itself_less_risky_than_its_effect():
    """The floor is enforced where the spec is built, not left to review."""
    spec = ToolSpec.of("mail.send", "Send a message.", effect=Effect.SEND, risk_level=RiskLevel.LOW)
    assert spec.risk_level is RiskLevel.HIGH


def test_a_spec_may_declare_itself_more_risky_than_its_effect():
    """A read of something sensitive is a real case, so raising is allowed."""
    spec = ToolSpec.of("vault.read", "Read a secret.", risk_level=RiskLevel.HIGH)
    assert spec.risk_level is RiskLevel.HIGH


# --- The threshold applies to everyone ----------------------------------------


def test_a_high_risk_action_waits_for_a_person_with_no_policy_declared():
    assert ask(Effect.SEND).decision is Decision.REQUIRE_APPROVAL


def test_an_ordinary_read_is_never_put_to_the_user():
    assert ask(Effect.READ).decision is Decision.ALLOW


def test_the_threshold_is_high():
    """Stated as a test because moving it silently changes every employee."""
    assert APPROVAL_THRESHOLD is RiskLevel.HIGH


# --- A declaration narrows and never widens -----------------------------------


def test_read_only_denies_a_write_the_threshold_would_have_allowed():
    decision = ask(Effect.WRITE, policies=frozenset({"read_only"}))
    assert decision.decision is Decision.DENY
    assert "read-only" in decision.reason


def test_no_sending_denies_the_send_rather_than_asking_about_it():
    """A declared restriction is not a question. Offering the user a chance to
    allow one call of it would make the declaration a suggestion."""
    assert ask(Effect.SEND, policies=frozenset({"no_sending"})).decision is Decision.DENY


def test_no_policy_can_allow_what_the_threshold_refuses():
    """The catalog is checked exhaustively: none of them may return ALLOW for a
    high-risk action, whatever else they say about it."""
    for name in CATALOG:
        decision = ask(Effect.SPEND, policies=frozenset({name}))
        assert decision.decision is not Decision.ALLOW, name


def test_the_strictest_rule_wins_regardless_of_declaration_order():
    both = frozenset({"no_irreversible_actions", "no_deleting"})
    assert ask(Effect.DELETE, policies=both).decision is Decision.DENY


def test_approve_every_write_asks_about_a_change_the_threshold_allows():
    decision = ask(Effect.WRITE, policies=frozenset({"approve_every_write"}))
    assert decision.decision is Decision.REQUIRE_APPROVAL


def test_a_policy_says_nothing_about_a_call_it_is_not_about():
    assert ask(Effect.READ, policies=frozenset({"no_spending"})).decision is Decision.ALLOW


def test_an_irreversible_action_waits_even_when_its_risk_is_low():
    decision = ask(
        Effect.WRITE,
        policies=frozenset({"no_irreversible_actions"}),
        reversible=False,
        risk_level=RiskLevel.LOW,
    )
    assert decision.decision is Decision.REQUIRE_APPROVAL


# --- The engine is a pure function --------------------------------------------


def test_the_same_request_decides_the_same_way_twice():
    """Not a tautology: it is what makes an audit line reproducible, and it
    fails the moment anyone reaches for a clock or a setting in here."""
    request = PolicyRequest(
        actor=ACTOR, action="code.run(...)", tool="code.run", effect=Effect.EXECUTE
    )
    assert ENGINE.evaluate(request) == ENGINE.evaluate(request)


# --- A wrong policy name is loud ----------------------------------------------


@pytest.mark.parametrize("name", ["no_sendng", "readonly", "NO_SENDING"])
def test_a_policy_name_no_rule_answers_to_fails_the_declaration(name):
    """The most expensive typo there is: it reads in the file as a restriction
    being enforced and is in fact nothing at all."""
    definition = EmployeeDefinition.create(
        "worker",
        Role("Worker"),
        allowed_tools=frozenset({"fs.read"}),
        policies=frozenset({name}),
    )
    issues = check(definition, {"fs.read": frozenset()})
    assert any(name in issue.message and issue.severity is Severity.ERROR for issue in issues)


def test_the_policies_the_shipped_employees_declare_all_exist():
    """The catalog and the four declarations, checked against each other."""
    from infrastructure.employees.yaml_registry import YamlEmployeeRegistry

    for definition in YamlEmployeeRegistry().list():
        assert definition.policies <= set(CATALOG), definition.name
