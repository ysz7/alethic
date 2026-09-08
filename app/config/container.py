"""The composition root: settings, adapters and the runtime meet here.

`infrastructure/container.py` builds adapters and knows nothing above itself.
Assembling the employee runtime needs both `application` and `infrastructure`,
and this is the one place allowed to see both - which is what a composition root
is for. See docs/adr/0001.
"""

from __future__ import annotations

from app.config.settings import Settings, get_settings
from application.alethic.delegation import CapabilityDelegator
from application.alethic.intent import IntentReader
from application.alethic.language import DEFAULT_LANGUAGE
from application.alethic.manager import AlethicManager
from application.alethic.planner import ObjectivePlanner
from application.alethic.reconciliation import Reconciler
from application.alethic.supervisor import Supervisor
from application.alethic.synthesis import Synthesizer
from application.alethic.verification import ObjectiveVerifier
from application.computer.screen_reader import LLMScreenReader
from application.employee_runtime.approvals import ApprovalGate
from application.employee_runtime.executor import Executor
from application.employee_runtime.planner import Planner
from application.employee_runtime.runtime import EmployeeRuntime, RuntimeDependencies
from application.employee_runtime.verifier import Verifier
from application.interface.activity import Activity
from application.interface.runs import Runs
from application.interface.service import (
    DEFAULT_LIMIT,
    AlethicService,
    ServiceDependencies,
)
from application.memory.assembler import ContextAssembler
from application.memory.consolidation import Consolidator
from application.memory.distiller import OutcomeDistiller
from application.memory.recorder import MemoryRecorder
from application.memory.workspace import WorkspaceMemory
from application.task_runner import TaskRunner
from application.validation.harness import ValidationHarness
from application.workflows.engine import WorkflowEngine
from domain.approvals.protocols import ApprovalWaiter
from domain.employees.definition import EmployeeDefinition
from infrastructure.container import Container


def build_container(settings: Settings | None = None, *, in_memory: bool = False) -> Container:
    """Build the container, and hand it the one dependency it cannot build.

    Reading a screen needs an application component (`LLMScreenReader`) and a
    model that only the container can route to. Neither layer may reach the
    other, so the wire is made here and passed as a callable: nothing is built,
    and no model is routed, for a run that never looks at a screen.
    """
    container = Container(settings or get_settings(), in_memory=in_memory)
    container.use_screen_reader(
        lambda: LLMScreenReader(container.llm_for(*LLMScreenReader.routing()))
    )
    return container


def build_memory(
    container: Container,
) -> tuple[ContextAssembler | None, MemoryRecorder | None]:
    """The two halves of memory, or neither.

    Neither when memory is switched off, and that is the whole of the difference
    it makes: the runtime takes both as optional, so a machine with memory off
    runs the Phase 8 loop rather than a degraded Phase 9 one.
    """
    memory = container.memory
    maintenance = container.memory_maintenance
    if memory is None or maintenance is None:
        return None, None
    settings = container.settings
    recorder = MemoryRecorder(
        memory,
        distiller=OutcomeDistiller(container.llm_for(*OutcomeDistiller.routing())),
        consolidator=Consolidator(
            container.llm_for(*Consolidator.routing()),
            memory,
            maintenance,
            threshold=settings.memory_consolidation_threshold,
        ),
    )
    return ContextAssembler(memory, limit=settings.memory_recall_limit), recorder


async def build_runtime(container: Container, definition: EmployeeDefinition) -> EmployeeRuntime:
    """Assemble the one runtime for a given employee declaration.

    Every employee gets the same three stages and the same loop. What differs is
    the declaration passed in: role, goals, tools, model profile, limits.
    """
    context, recorder = build_memory(container)
    return EmployeeRuntime(
        definition,
        RuntimeDependencies(
            planner=Planner(container.llm_for(*Planner.routing())),
            executor=Executor(
                container.llm_for(*Executor.routing(definition)),
                container.tool_registry,
                limits=definition.limits,
                approvals=ApprovalGate(container.approval_service, audit=container.audit),
                call_log=container.tool_call_log,
                audit=container.audit,
                progress=container.progress,
                cancellation=container.cancellations,
            ),
            verifier=Verifier(container.llm_for(*Verifier.routing())),
            tasks=container.task_repository,
            tools=container.tool_registry,
            limits=definition.limits,
            system_prompt=definition.system_prompt,
            progress=container.progress,
            context=context,
            recorder=recorder,
        ),
    )


def build_manager(container: Container) -> AlethicManager:
    """Assemble Alethic.

    Six model-facing components, each routed for what it is: comprehension and
    decomposition get a good model, choosing from a short list gets a cheap one,
    judging - the verdict and deciding which of two people is right - is held
    above the bottom of the catalog, and the answer the user reads gets a good
    model again. None of them names a model, and none of them names an employee -
    the workforce arrives from the registry and the work is done through
    `TaskExecution`, which is the task runner.
    """
    registry = container.employee_registry
    _, recorder = build_memory(container)
    # The one setting the manager needs. Read here rather than inside
    # `application/`, which is not allowed to know a settings object exists.
    language = getattr(container.settings, "response_language", DEFAULT_LANGUAGE)
    return AlethicManager(
        intent=IntentReader(
            container.llm_for(*IntentReader.routing()), language=language
        ),
        planner=ObjectivePlanner(container.llm_for(*ObjectivePlanner.routing())),
        supervisor=Supervisor(
            execution=build_task_runner(container),
            delegator=CapabilityDelegator(
                container.llm_for(*CapabilityDelegator.routing()), registry
            ),
            progress=container.progress,
        ),
        verifier=ObjectiveVerifier(container.llm_for(*ObjectiveVerifier.routing())),
        synthesizer=Synthesizer(
            container.llm_for(*Synthesizer.routing()), language=language
        ),
        reconciler=Reconciler(container.llm_for(*Reconciler.routing())),
        registry=registry,
        objectives=container.objective_repository,
        plans=container.plan_repository,
        progress=container.progress,
        memory=(
            WorkspaceMemory(container.memory, recorder)
            if container.memory is not None and recorder is not None
            else None
        ),
    )


def build_task_runner(container: Container) -> TaskRunner:
    async def _runtime(definition: EmployeeDefinition) -> EmployeeRuntime:
        return await build_runtime(container, definition)

    return TaskRunner(
        tasks=container.task_repository,
        assignments=container.assignment_repository,
        registry=container.employee_registry,
        build_runtime=_runtime,
        progress=container.progress,
    )


def build_service(
    container: Container, waiter: ApprovalWaiter, *, history_limit: int = DEFAULT_LIMIT
) -> AlethicService:
    """Assemble the boundary every interface talks to.

    The waiter is passed in rather than read off the container because it is a
    property of the *interface*, not of the machine: a terminal answers an
    approval on the call stack that asked, a page answers it from a request
    arriving later, and whoever built the surface is the only one who knows
    which. Nothing else here differs between one interface and the next.
    """
    return AlethicService(
        ServiceDependencies(
            runs=Runs(
                runner=build_task_runner(container),
                manager=build_manager(container),
                tasks=container.task_repository,
                cancellations=container.cancellations,
                approvals=waiter,
            ),
            activity=Activity(
                container.progress,
                tasks=container.task_repository,
                objectives=container.objective_repository,
                plans=container.plan_repository,
            ),
            conversations=container.conversation_repository,
            objectives=container.objective_repository,
            plans=container.plan_repository,
            tasks=container.task_repository,
            employees=container.employee_registry,
            approvals=container.approval_repository,
            waiter=waiter,
            tool_calls=container.tool_call_log,
            llm_calls=container.llm_call_log,
            approval_service=container.approval_service,
            history_limit=history_limit,
        )
    )


def build_workflow_engine(container: Container) -> WorkflowEngine:
    """A workflow runs through the same runner every other task does.

    That is the whole point of the engine being three lines: a predefined
    process and a plan Alethic invented differ in where the decomposition came
    from and in nothing below it - same employees, same limits, same gate.
    """
    return WorkflowEngine(
        container.workflow_registry,
        build_task_runner(container),
        container.workflow_runs,
    )


def build_harness(container: Container) -> ValidationHarness:
    """Assemble the validation harness with all three of the platform's doors.

    It gets the manager, the task runner and the workflow engine - the same
    three objects the CLI builds for `ask-alethic`, `run-task` and
    `run-workflow` - and nothing else that can do work. Everything else handed
    in here is a way of reading what happened afterwards.
    """
    return ValidationHarness(
        scenarios=container.scenario_registry,
        runs=container.validation_runs,
        tasks=container.task_repository,
        workspace=container.settings.ensure_workspace_dir(),
        available=container.available_requirements(),
        objectives=build_manager(container),
        employees=build_task_runner(container),
        workflows=build_workflow_engine(container),
        tool_calls=container.tool_call_log,
        audit=container.audit,  # type: ignore[arg-type]
        approvals=container.approval_repository,
        memory=container.memory,
    )
