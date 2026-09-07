"""Phase 10's Definition of Done, checked the only way that means anything.

*Any HIGH action is blocked until approval; a rejected action does not happen
and appears in the audit as DENIED; a new workflow is added without editing any
employee.*

Three tests, one per clause. The third one writes a workflow into a temporary
directory and runs it - if it ever needs a line of Python somewhere else to
pass, the Definition of Done has been broken and this is where it shows.
"""

from __future__ import annotations

from pathlib import Path

from application.employee_runtime.approvals import ApprovalGate
from application.employee_runtime.executor import Executor
from application.employee_runtime.transcript import Transcript
from application.workflows.engine import WorkflowEngine
from domain.approvals.models import Approval, ApprovalState
from domain.llm.models import ToolCallRequest
from domain.policies.risk import Effect
from domain.tasks.task import Task, TaskResult, TaskStatus
from domain.workflows.run import RunStatus
from infrastructure.approvals.service import ApprovalMode, LocalApprovalService
from infrastructure.persistence.approval_repository import InMemoryApprovalRepository
from infrastructure.persistence.audit_repository import InMemoryAuditLog
from infrastructure.persistence.workflow_repository import InMemoryWorkflowRunRepository
from infrastructure.tools.registry import InMemoryToolRegistry
from infrastructure.workflows.yaml_registry import YamlWorkflowRegistry
from tests.fakes.employees import definition
from tests.fakes.llm import FakeLLM, reply, tool_reply
from tests.fakes.tools import FakeTool

#: A tool that moves money. Nothing about it is special except its effect, which
#: is the whole point: HIGH is derived, not declared by hand.
PAYMENT = dict(effect=Effect.SPEND, reversible=False)


def executor(tool: FakeTool, service, audit: InMemoryAuditLog) -> Executor:
    llm = FakeLLM(
        [
            tool_reply(ToolCallRequest(id="1", name=tool.spec.name, arguments={"amount": 10})),
            reply("I could not do that."),
        ]
    )
    return Executor(
        llm,
        InMemoryToolRegistry([tool]),
        approvals=ApprovalGate(service, audit=audit),
        audit=audit,
    )


# --- Any HIGH action waits for a person ---------------------------------------


async def test_a_high_risk_action_does_not_happen_until_somebody_says_yes() -> None:
    tool = FakeTool("bank.pay", **PAYMENT)
    approvals = InMemoryApprovalRepository()
    asked: list[str] = []

    service = LocalApprovalService(
        approvals,
        mode=ApprovalMode.PROMPT,
        confirmer=lambda request: asked.append(request.action) or True,
        is_interactive=lambda: True,
    )
    audit = InMemoryAuditLog()
    who = definition(tools={"bank.pay"}, policies={"no_irreversible_actions"})

    await executor(tool, service, audit).run(Task.create("pay the invoice"), who, Transcript())

    # It ran, and it ran only after the question was put and answered.
    assert len(asked) == 1
    assert tool.calls == [{"amount": 10}]
    stored = await approvals.list_pending()
    assert stored == []  # answered, not left hanging


async def test_with_nobody_to_ask_the_high_risk_action_simply_does_not_happen() -> None:
    """The rule the whole design rests on: silence is not consent."""
    tool = FakeTool("bank.pay", **PAYMENT)
    audit = InMemoryAuditLog()

    outcome = await executor(tool, None, audit).run(
        Task.create("pay the invoice"), definition(tools={"bank.pay"}), Transcript()
    )

    assert tool.calls == []
    assert outcome.finished
    assert [record.result for record in audit.records] == ["DENIED"]


# --- A refused action is not done, and is recorded as refused -----------------


async def test_a_rejected_action_does_not_run_and_is_audited_as_denied() -> None:
    tool = FakeTool("bank.pay", **PAYMENT)
    approvals = InMemoryApprovalRepository()
    service = LocalApprovalService(
        approvals,
        mode=ApprovalMode.PROMPT,
        confirmer=lambda _: False,
        is_interactive=lambda: True,
    )
    audit = InMemoryAuditLog()

    await executor(tool, service, audit).run(
        Task.create("pay the invoice"), definition(tools={"bank.pay"}), Transcript()
    )

    assert tool.calls == []
    denied = [record for record in audit.records if record.result == "DENIED"]
    assert len(denied) == 1
    assert denied[0].tool == "bank.pay"
    assert denied[0].details["effect"] == Effect.SPEND.value


async def test_an_action_a_declared_policy_forbids_is_never_even_asked_about() -> None:
    """A declaration is not a suggestion: nobody is offered the chance to allow
    one call of something the employee was declared not to do."""
    tool = FakeTool("bank.pay", **PAYMENT)
    asked: list[str] = []
    service = LocalApprovalService(
        InMemoryApprovalRepository(),
        mode=ApprovalMode.PROMPT,
        confirmer=lambda request: asked.append(request.action) or True,
        is_interactive=lambda: True,
    )
    audit = InMemoryAuditLog()
    who = definition(tools={"bank.pay"}, policies={"no_spending"})

    await executor(tool, service, audit).run(Task.create("pay the invoice"), who, Transcript())

    assert asked == []
    assert tool.calls == []
    assert [record.result for record in audit.records] == ["DENIED"]


async def test_what_did_run_is_audited_too_so_the_two_can_be_counted_together() -> None:
    tool = FakeTool("fs.read", effect=Effect.READ)
    audit = InMemoryAuditLog()

    await executor(tool, None, audit).run(
        Task.create("read the file"), definition(tools={"fs.read"}), Transcript()
    )

    assert [record.result for record in audit.records] == ["SUCCESS"]
    assert audit.records[0].tool == "fs.read"


# --- A new workflow needs no change to any employee ---------------------------

#: The entire change. One file, three lines of it that matter.
NIGHTLY = """
name: nightly
description: Tidy the folder and say what changed.
trigger: MANUAL
inputs:
  folder: notes
steps:
  - name: tidy
    employee: organizer
    instruction: Put {folder} in order.
  - name: report
    employee: researcher
    depends_on: [tidy]
    instruction: >
      Write up what changed. The tidying said: {steps.tidy}
"""


class Runner:
    """Implements `StepExecution` - the same contract the real runner satisfies."""

    def __init__(self) -> None:
        self.given: list[tuple[str, str]] = []

    async def submit_and_run(self, goal: str, employee_name: str, **kwargs: object) -> Task:
        self.given.append((employee_name, goal))
        task = Task.create(goal).transition_to(TaskStatus.RUNNING)[0]
        return task.transition_to(TaskStatus.VERIFYING)[0].complete(
            TaskResult(summary=f"{employee_name} finished")
        )[0]


async def test_a_workflow_declared_in_a_file_runs_with_no_edit_to_any_employee(
    tmp_path: Path,
) -> None:
    (tmp_path / "nightly.yaml").write_text(NIGHTLY, encoding="utf-8")
    runner = Runner()
    engine = WorkflowEngine(
        YamlWorkflowRegistry(tmp_path), runner, InMemoryWorkflowRunRepository()
    )

    run = await engine.run("nightly", inputs={"folder": "sales"})

    assert run.status is RunStatus.COMPLETED
    assert [who for who, _ in runner.given] == ["organizer", "researcher"]
    assert runner.given[0][1] == "Put sales in order."
    assert "organizer finished" in runner.given[1][1]


async def test_the_workflows_that_ship_name_employees_that_exist() -> None:
    """A workflow naming an employee nobody declared is work that arrives
    nowhere, and it is checkable before a run rather than three steps into one.
    """
    from infrastructure.employees.yaml_registry import YamlEmployeeRegistry

    declared = {employee.name for employee in YamlEmployeeRegistry().list()}
    for workflow in YamlWorkflowRegistry().list_all():
        assert workflow.employees <= declared, workflow.name


async def test_a_pending_question_is_written_down_before_it_is_answered() -> None:
    """A process killed mid-question leaves a row, which is what makes the
    question survivable rather than lost."""
    approvals = InMemoryApprovalRepository()
    seen: list[list[Approval]] = []

    async def look(_request) -> bool:
        seen.append(await approvals.list_pending())
        return True

    service = LocalApprovalService(
        approvals, mode=ApprovalMode.PROMPT, confirmer=look, is_interactive=lambda: True
    )
    audit = InMemoryAuditLog()
    tool = FakeTool("bank.pay", **PAYMENT)

    await executor(tool, service, audit).run(
        Task.create("pay"), definition(tools={"bank.pay"}), Transcript()
    )

    assert seen and seen[0] and seen[0][0].state is ApprovalState.PENDING
