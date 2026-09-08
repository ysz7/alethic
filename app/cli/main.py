"""The command line, and the command that opens the local interface.

Since Phase 6 the CLI is no longer the only surface: `alethic serve` starts the
local interface, which is where a task is normally run and watched. Everything
here still works on its own, because a machine with no browser, or a run started
from a script, must not need one.
"""

from __future__ import annotations

import asyncio
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path
from uuid import UUID

import typer

from app.config.container import (
    build_container,
    build_harness,
    build_manager,
    build_task_runner,
    build_workflow_engine,
)
from app.config.settings import get_settings
from domain.approvals.models import ApprovalState
from domain.errors import AlethicError, StorageNotInitializedError
from domain.llm.models import LLMRequest, Message, RoutingHints, TaskKind
from domain.policies.models import ActorKind, SimpleActor
from domain.validation.failures import FailureKind
from domain.validation.reliability import Verdict, build_report, reliability_of
from domain.validation.run import RunStatus

app = typer.Typer(
    name="alethic",
    help="Alethic - run digital employees on your own machine.",
    no_args_is_help=True,
    add_completion=False,
)


def _version() -> str:
    try:
        return package_version("alethic")
    except PackageNotFoundError:
        return "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"alethic {_version()}")
        raise typer.Exit


@app.callback()
def main(
    _version_flag: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Alethic command line."""


@app.command()
def config() -> None:
    """Show the resolved configuration, with secrets masked."""
    settings = get_settings()
    typer.echo(f"data_dir:      {settings.data_dir}")
    typer.echo(f"database:      {settings.resolved_database_url}")
    typer.echo(f"workspace:     {settings.resolved_workspace_dir}")
    typer.echo(f"approvals:     {settings.approval_mode}")
    typer.echo(f"interface:     http://{settings.ui_host}:{settings.ui_port}  (alethic serve)")
    typer.echo(
        f"computer use:  {'on' if settings.computer_use_enabled else 'off'} "
        f"(desktop; the browser surface follows the browser tools)"
    )
    typer.echo(
        f"memory:        {'on' if settings.memory_enabled else 'off'}"
        f"  (recall {settings.memory_recall_limit})"
    )
    typer.echo(f"stop file:     {settings.stop_file_path}")
    typer.echo(f"llm_base_url:  {settings.llm_base_url}")
    typer.echo(f"llm_api_key:   {'set' if settings.llm_api_key else 'not set'}")
    typer.echo(f"default_model: {settings.llm_default_model}")
    typer.echo(f"log:           {settings.log_level} ({settings.log_format})")


@app.command()
def tasks() -> None:
    """List the tasks that would be picked up again after a restart."""

    async def _run() -> None:
        container = build_container()
        try:
            try:
                resumable = await container.task_repository.list_resumable()
            except StorageNotInitializedError as error:
                # A fresh checkout has no schema yet; say so instead of a stack trace.
                typer.secho(
                    f"{error} Run: uv run alembic upgrade head", fg="red", err=True
                )
                raise typer.Exit(code=1) from error
            if not resumable:
                typer.echo("No resumable tasks.")
                return
            for task in resumable:
                typer.echo(f"{task.id}  {task.status:<20} {task.goal}")
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def ask(
    question: str = typer.Argument(..., help="What to ask."),
    system: str = typer.Option(
        "", "--system", "-s", help="Optional system prompt."
    ),
) -> None:
    """Ask a model a question and report what it cost.

    This is Phase 2's validation: a real answer through a real provider, with
    the price of it on screen. Cost is shown from the first call because local
    development pays for every token.
    """

    async def _run() -> None:
        container = build_container()
        try:
            settings = container.settings
            client = container.llm_for(
                TaskKind.CONVERSATION, hints=RoutingHints(quality=0.7)
            )
            messages = [Message.user(question)]
            if system:
                messages.insert(0, Message.system(system))
            elif settings.response_language != "en":
                messages.insert(
                    0, Message.system(f"Answer in {settings.response_language}.")
                )

            response = await client.generate(
                LLMRequest(messages=tuple(messages), temperature=0.3)
            )
            typer.echo(response.content)
            usage = response.usage
            typer.secho(
                f"\n[{response.model}] {usage.prompt_tokens} in / {usage.output_tokens} out"
                f" - ${usage.cost_usd:.6f} - {usage.latency_ms} ms",
                fg="cyan",
            )
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def spend() -> None:
    """Show what has been spent on models so far."""

    async def _run() -> None:
        container = build_container()
        try:
            summary = await container.llm_call_log.total()
            typer.echo(f"calls:         {summary.calls}")
            typer.echo(f"prompt tokens: {summary.prompt_tokens}")
            typer.echo(f"output tokens: {summary.output_tokens}")
            typer.echo(f"cost:          ${summary.cost_usd:.6f}")
        except StorageNotInitializedError as error:
            typer.secho(
                f"{error} Run: uv run alembic upgrade head", fg="red", err=True
            )
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def models() -> None:
    """Show the model catalog and which entry each kind of work defaults to."""
    container = build_container()
    catalog = container.model_catalog
    defaults = {name: kind for kind, name in catalog.defaults.items()}

    for entry in catalog.entries:
        default_for = [k.value.lower() for k, n in catalog.defaults.items() if n == entry.name]
        marker = f"  <- default for {', '.join(sorted(default_for))}" if default_for else ""
        typer.echo(f"{entry.name:<10} {entry.provider}/{entry.model}{marker}")
        typer.echo(
            f"           ${entry.input_cost_per_1k_usd}/1k in, "
            f"${entry.output_cost_per_1k_usd}/1k out, "
            f"{entry.context_tokens} ctx"
        )
    if not defaults:
        typer.echo("No defaults configured.")


@app.command(name="ask-alethic")
def ask_alethic(
    objective: str = typer.Argument(..., help="What you want, in your own words."),
) -> None:
    """Give Alethic a goal. It decides what has to happen and who does it.

    This is the normal way in from Phase 7 on: `run-task` still exists and still
    hands work to a named employee, but choosing the employee is the manager's
    job, not the user's.
    """

    async def _run() -> None:
        container = build_container()
        try:
            await container.sync_employees()
            manager = build_manager(container)
            received = await manager.receive(objective)
            result = await manager.handle_objective(received)
            _report_objective(result)
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def objectives() -> None:
    """What has been asked of Alethic here, newest first."""

    async def _run() -> None:
        container = build_container()
        try:
            recent = await container.objective_repository.list_recent(limit=20)
            if not recent:
                typer.echo("Nothing has been asked yet.")
                return
            for item in recent:
                colour = {"DONE": "green", "FAILED": "red", "ESCALATED": "yellow"}.get(
                    item.status.value, "white"
                )
                typer.secho(f"{item.status.value:<10}", fg=colour, nl=False)
                typer.echo(f"{item.id}  {item.text[:70]}")
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def memory(
    search: str = typer.Option("", "--search", "-s", help="Words to look for."),
    limit: int = typer.Option(20, "--limit", "-n", help="How many to show."),
    prune: bool = typer.Option(
        False, "--prune", help="Drop what has passed its time to live, and show what is left."
    ),
) -> None:
    """What this workspace remembers.

    Read through the same contract everything else reads memory through: this
    command has no more access to the store than a running task does, which is
    why it shows workspace memory and not an employee's private notes.
    """

    async def _run() -> None:
        from domain.memory.models import MemoryQuery, MemoryScope

        container = build_container()
        try:
            store = container.memory
            if store is None:
                typer.echo("Memory is switched off (ALETHIC_FLAGS__MEMORY=false).")
                return
            if prune:
                maintenance = container.memory_maintenance
                dropped = await maintenance.prune() if maintenance else 0
                typer.echo(f"Forgot {dropped} expired item(s).")
            items = await store.recall(
                MemoryQuery(
                    text=search,
                    scopes=frozenset({MemoryScope.WORKSPACE}),
                    limit=limit,
                )
            )
            if not items:
                typer.echo("Nothing remembered yet." if not search else "Nothing matched.")
                return
            for item in items:
                typer.secho(f"{item.kind.value:<11}", fg="cyan", nl=False)
                typer.echo(
                    f"{item.created_at:%Y-%m-%d %H:%M}  "
                    f"{' '.join(item.content.split())[:90]}"
                )
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command(name="run-task")
def run_task(
    goal: str = typer.Argument(..., help="What you want done."),
    employee: str = typer.Option("researcher", "--employee", "-e", help="Who should do it."),
) -> None:
    """Give a task to a digital employee and wait for the result."""

    async def _run() -> None:
        container = build_container()
        try:
            await container.sync_employees()
            runner = build_task_runner(container)
            task = await runner.submit_and_run(goal, employee)
            _report(task)
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def resume() -> None:
    """Pick up every task that was interrupted, from where it stopped."""

    async def _run() -> None:
        container = build_container()
        try:
            await container.sync_employees()
            runner = build_task_runner(container)
            pending = await runner.resumable()
            if not pending:
                typer.echo("Nothing to resume.")
                return
            typer.echo(f"Resuming {len(pending)} task(s).")
            for task in pending:
                typer.secho(f"\n-> {task.goal}", fg="cyan")
                _report(await runner.resume(task))
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def employees(
    strict: bool = typer.Option(
        False, "--strict", help="Exit non-zero if any declaration has a problem."
    ),
) -> None:
    """List the declared employees, and say what is wrong with any of them.

    Each one is a directory under `employees/`. Nothing here reads a class name.

    The checks are the quiet failures: a tool this machine does not offer, a
    capability nothing backs, work that will never be routed here because it was
    not declared. None of them raises at runtime - the employee just does worse
    for a reason nobody can see - so they are printed where somebody will look.
    """
    container = build_container()
    declared = container.employee_registry.list()
    if not declared:
        typer.echo("No employees declared.")
        return
    for definition in declared:
        typer.secho(f"{definition.name}", fg="cyan", nl=False)
        typer.echo(f"  {definition.role.title}")
        typer.echo(f"  tools:  {', '.join(sorted(definition.allowed_tools)) or 'none'}")
        can_do = ", ".join(sorted(c.value for c in definition.capabilities))
        typer.echo(f"  can do: {can_do or 'nothing declared'}")
        typer.echo(
            f"  limits: {definition.limits.max_steps} steps, "
            f"${definition.limits.max_cost_usd}, "
            f"{definition.limits.max_wall_time_seconds:.0f}s"
        )

    issues = container.check_employees()
    if issues:
        typer.echo("")
        for issue in issues:
            colour = "red" if issue.is_error else "yellow"
            typer.secho(f"{issue.severity.value:<8}", fg=colour, nl=False)
            typer.echo(f"{issue.employee}: {issue.message}")
    if strict and issues:
        raise typer.Exit(code=1)


@app.command()
def tools() -> None:
    """Show the tools this machine offers, and who is allowed to call them.

    Least privilege is not a claim to take on trust: this prints, per tool, the
    employees that listed it. A tool nobody lists is a tool nobody can call.
    """
    container = build_container()
    declared = container.employee_registry.list()
    everything = SimpleActor("cli", ActorKind.USER, frozenset({"*"}))

    for spec in container.tool_registry.list_specs(everything):
        users = sorted(d.name for d in declared if spec.name in d.allowed_tools)
        gate = "" if spec.reversible else "  [needs approval]"
        typer.secho(f"{spec.name:<16}", fg="cyan", nl=False)
        typer.echo(
            f"{spec.risk_level.value:<8}{spec.interface_level.value:<14}"
            f"{', '.join(users) or 'nobody'}{gate}"
        )
        typer.echo(f"                 {spec.description.splitlines()[0]}")


@app.command()
def stop(
    reason: str = typer.Option("", "--reason", "-r", help="Why, shown to the employee."),
    clear: bool = typer.Option(False, "--clear", help="Release the brake instead."),
) -> None:
    """Stop anything that is acting on a screen, right now.

    Deliberately not a signal to a process: it writes a file that every action
    on a screen reads before it happens. So it works from a second terminal
    while the first one is busy, it works when the run has the screen, and a
    stop set while nothing is running still holds when the next run starts.
    """
    from infrastructure.computer.stop import FileStopSignal

    signal = FileStopSignal(get_settings().stop_file_path)
    if clear:
        released = signal.release()
        typer.echo(
            "Computer use released." if released else "Computer use was not stopped."
        )
        return
    path = signal.engage(reason)
    typer.secho(f"Computer use stopped: {signal.reason}", fg="yellow")
    typer.echo(f"Release it with: alethic stop --clear   ({path})")


@app.command()
def serve(
    host: str = typer.Option("", "--host", help="Override the bind address."),
    port: int = typer.Option(0, "--port", "-p", help="Override the port."),
    reload: bool = typer.Option(False, "--reload", help="Restart on source changes."),
) -> None:
    """Open the local interface: run tasks, watch them, and approve actions.

    One command, one process: the server, the employee runtime and the database
    are the same thing, which is what lets the page park a tool call on a
    question and answer it from a button.
    """
    import uvicorn

    settings = get_settings()
    bind = host or settings.ui_host
    on = port or settings.ui_port
    typer.secho(f"Alethic on http://{bind}:{on}", fg="cyan")
    if bind not in ("127.0.0.1", "localhost", "::1"):
        # Said once, plainly. The interface starts tasks and approves
        # irreversible actions, and it has no authentication because nothing
        # off this machine is supposed to reach it.
        typer.secho(
            f"Warning: {bind} is not loopback. This interface has no "
            "authentication and can start tasks on this machine.",
            fg="yellow",
            err=True,
        )
    uvicorn.run(
        "app.ui.server:create_app",
        factory=True,
        host=bind,
        port=on,
        reload=reload,
        log_level=settings.log_level.lower(),
    )


@app.command()
def approvals() -> None:
    """List the irreversible actions still waiting on a decision."""

    async def _run() -> None:
        container = build_container()
        try:
            pending = await container.approval_repository.list_pending()
            if not pending:
                typer.echo("Nothing is waiting for approval.")
                return
            for approval in pending:
                request = approval.request
                typer.secho(f"{request.id}", fg="yellow")
                typer.echo(f"  action: {request.action}")
                typer.echo(f"  risk:   {request.risk_level.value}")
                typer.echo(f"  task:   {request.task_id}")
                if request.reason:
                    typer.echo(f"  why:    {request.reason}")
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def approve(
    approval_id: str = typer.Argument(..., help="The id shown by `alethic approvals`."),
    comment: str = typer.Option("", "--comment", "-c", help="Why."),
) -> None:
    """Approve a pending action."""
    _resolve(approval_id, ApprovalState.APPROVED, comment)


@app.command()
def reject(
    approval_id: str = typer.Argument(..., help="The id shown by `alethic approvals`."),
    comment: str = typer.Option("", "--comment", "-c", help="Why."),
) -> None:
    """Reject a pending action."""
    _resolve(approval_id, ApprovalState.REJECTED, comment)


@app.command()
def policies() -> None:
    """The rules an employee declaration can opt into, and who opted in.

    Printed rather than documented, because a policy that is written down in
    prose and not in the catalog enforces nothing - and this is the list the
    engine actually reads.
    """
    from domain.policies.risk import EFFECT_RISK
    from domain.policies.rules import APPROVAL_THRESHOLD, CATALOG

    container = build_container()
    declared = container.employee_registry.list()

    typer.secho("Risk follows the effect", fg="cyan")
    for effect, level in EFFECT_RISK.items():
        waits = "  waits for a person" if level.value == APPROVAL_THRESHOLD.value else ""
        typer.echo(f"  {effect.value:<10}{level.value}{waits}")
    typer.echo(f"\nAt {APPROVAL_THRESHOLD.value} and above, a person decides.\n")

    typer.secho("Declared policies", fg="cyan")
    for name, rule in sorted(CATALOG.items()):
        users = sorted(d.name for d in declared if name in d.policies)
        typer.secho(f"  {name:<26}", fg="yellow", nl=False)
        typer.echo(f"{rule.category.value:<16}{', '.join(users) or 'nobody'}")
        typer.echo(f"    {rule.description}")


@app.command()
def audit(
    limit: int = typer.Option(30, "--limit", "-n", help="How many lines to show."),
    task: str = typer.Option("", "--task", "-t", help="Only this task's actions."),
) -> None:
    """What was done on this machine, newest first.

    Distinct from `alethic spend`, which is what the models cost, and from the
    trace, which is what one run did. This is the list that includes the actions
    that did *not* happen - the ones a policy denied or the user refused.
    """

    async def _run() -> None:
        container = build_container()
        try:
            trail = container.audit
            records = await trail.recent(  # type: ignore[attr-defined]
                limit=limit, task_id=UUID(task) if task else None
            )
            if not records:
                typer.echo("Nothing has been recorded here yet.")
                return
            colours = {"SUCCESS": "green", "FAILURE": "red", "DENIED": "yellow"}
            for record in records:
                when = record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                typer.secho(f"{record.result:<8}", fg=colours.get(record.result, "white"), nl=False)
                typer.echo(f"{when}  {record.actor_kind.value.lower()}  {record.action}")
                reason = record.details.get("reason")
                if reason:
                    typer.echo(f"          why: {reason}")
        except ValueError as error:
            typer.secho(f"'{task}' is not a task id.", fg="red", err=True)
            raise typer.Exit(code=1) from error
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def prompts() -> None:
    """The prompt assets that ship here: name, versions, and what is current.

    The digest is the point (§121). A version number says which file was used;
    the hash says whether that file is still the text it was, which is the
    difference between two runs being comparable and merely looking it.
    """
    from application import prompts as registry

    found = registry.catalog()
    if not found:
        typer.echo("No prompts are shipped here.")
        return
    for info in found:
        typer.secho(f"{info.name:<22}", fg="cyan", nl=False)
        typer.echo(f"{info.latest:<6}{info.digest}   [{', '.join(info.versions)}]")


@app.command()
def workflows() -> None:
    """The predefined processes declared here, and whether they can run.

    A workflow names employees by name. Whether those employees exist on this
    machine is the question worth answering before a run rather than three steps
    into one, so it is answered here.
    """
    settings = get_settings()
    if not settings.workflows_enabled:
        typer.echo("Workflows are switched off (ALETHIC_FLAGS__WORKFLOWS=false).")
        return
    container = build_container()
    declared = {d.name for d in container.employee_registry.list()}
    found = container.workflow_registry.list_all()
    if not found:
        typer.echo("No workflows are declared here. Add one under `workflows/`.")
        return
    for definition in found:
        missing = sorted(definition.employees - declared)
        typer.secho(f"{definition.name}", fg="cyan", nl=False)
        typer.echo(f"  {definition.trigger.value.lower()}, {len(definition.steps)} step(s)")
        if definition.description:
            typer.echo(f"  {definition.description.splitlines()[0]}")
        for step in definition.steps:
            after = f" after {', '.join(step.depends_on)}" if step.depends_on else ""
            retry = f" x{step.max_attempts}" if step.max_attempts > 1 else ""
            typer.echo(f"    {step.name:<14}{step.employee}{after}{retry}")
        if missing:
            typer.secho(
                f"  needs {', '.join(missing)}, which is not declared here.", fg="red"
            )


#: Declared once, because ruff will not have a call in a default and typer
#: needs one. The same shape every other repeatable option would take.
_INPUT_OPTION = typer.Option(
    [], "--input", "-i", help="key=value, repeatable. Overrides the declared default."
)


@app.command(name="run-workflow")
def run_workflow(
    name: str = typer.Argument(..., help="The workflow to run, from `alethic workflows`."),
    inputs: list[str] = _INPUT_OPTION,
) -> None:
    """Run a predefined process and report what each step produced."""

    if not get_settings().workflows_enabled:
        typer.secho("Workflows are switched off (ALETHIC_FLAGS__WORKFLOWS=false).", fg="red")
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            await container.sync_employees()
            values: dict[str, object] = {}
            for entry in inputs:
                key, separator, value = entry.partition("=")
                if not separator:
                    typer.secho(f"--input {entry} is not key=value.", fg="red", err=True)
                    raise typer.Exit(code=1)
                values[key.strip()] = value
            engine = build_workflow_engine(container)
            run = await engine.run(name, inputs=values)
            colour = "green" if run.succeeded else "red"
            typer.secho(f"\n{run.status.value}: {run.workflow}", fg=colour)
            for step in run.steps:
                mark = "ok " if step.succeeded else "no "
                typer.echo(f"  {mark}{step.step:<14}{step.employee}  ({step.attempts} attempt(s))")
                if step.summary:
                    typer.echo(f"      {step.summary.splitlines()[0][:100]}")
            if not run.succeeded:
                raise typer.Exit(code=1)
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def scenarios() -> None:
    """The real tasks the platform is measured on, and how each has gone here.

    A scenario is a request somebody actually wanted made, declared so it can be
    made again. The verdict beside each one comes from the runs recorded on this
    machine - not from a promise in a document.
    """

    async def _run() -> None:
        container = build_container()
        try:
            declared = container.scenario_registry.list_all()
            if not declared:
                typer.echo("No scenarios are declared here. Add one under `validation/scenarios/`.")
                return
            available = container.available_requirements()
            history = await _history(container)
            for scenario in declared:
                entry = reliability_of(scenario.name, history)
                missing = scenario.missing_requirements(available)
                typer.secho(f"{scenario.name:<30}", fg="cyan", nl=False)
                typer.secho(
                    f"{entry.verdict.value:<12}",
                    fg=_VERDICT_COLOURS.get(entry.verdict, "white"),
                    nl=False,
                )
                door = scenario.entry.value.lower()
                target = f" {scenario.target}" if scenario.target else ""
                typer.echo(f"phase {scenario.phase:<3}{door}{target}")
                if scenario.description:
                    typer.echo(f"  {scenario.description.splitlines()[0]}")
                if entry.attempts:
                    typer.echo(
                        f"  {entry.passes}/{entry.attempts} passed"
                        + (
                            f", usually {entry.common_failure.value}"
                            if entry.common_failure is not FailureKind.NONE
                            else ""
                        )
                    )
                if missing:
                    typer.secho(
                        "  needs " + ", ".join(item.value.lower() for item in missing)
                        + ", which is off here.",
                        fg="yellow",
                    )
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command()
def validate(
    name: str = typer.Argument("", help="One scenario. Omit to run the whole set."),
    regression: bool = typer.Option(
        False,
        "--regression",
        "-r",
        help="Only the scenarios that have passed here before (§11.5).",
    ),
    tag: str = typer.Option("", "--tag", "-t", help="Only scenarios carrying this tag."),
    phase: int = typer.Option(0, "--phase", "-p", help="Only scenarios for this phase."),
) -> None:
    """Give the platform real work and record what happened.

    This is not the test suite. `uv run pytest` says the platform still does
    what it was built to do; this says whether that is worth anything on a
    request somebody actually made. It costs money and takes minutes, which is
    why it is a command rather than something CI runs.
    """

    async def _run() -> None:
        container = build_container()
        try:
            await container.sync_employees()
            chosen = await _chosen(container, name, regression=regression, tag=tag, phase=phase)
            if not chosen:
                typer.echo("Nothing matched. `alethic scenarios` lists what is declared.")
                raise typer.Exit(code=1)

            harness = build_harness(container)
            failures = 0
            for scenario in chosen:
                typer.secho(f"\n> {scenario.name}", fg="cyan")
                # A workflow scenario has no request of its own - the process
                # is the request - so there is not always a first line to show.
                first = next(iter(scenario.request.splitlines()), scenario.target)
                typer.echo(f"  {first[:96]}")
                run = await harness.run_scenario(scenario)
                _report_validation(run)
                if run.status is RunStatus.FAILED:
                    failures += 1

            typer.echo("")
            typer.secho(
                f"{len(chosen) - failures}/{len(chosen)} passed.",
                fg="green" if not failures else "yellow",
            )
            if failures:
                raise typer.Exit(code=1)
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


@app.command(name="validation-report")
def validation_report(
    write: str = typer.Option(
        "", "--write", "-w", help="Also write the Markdown to this file."
    ),
) -> None:
    """What works reliably here, what works sometimes, and what does not work.

    Phase 11's Definition of Done, computed from the recorded runs rather than
    asserted. A capability that has succeeded once is not reliable, and this
    says so.
    """
    from application.validation.report import render

    async def _run() -> None:
        container = build_container()
        try:
            history = await _history(container)
            declared = [scenario.name for scenario in container.scenario_registry.list_all()]
            text = render(build_report(declared, history))
            typer.echo(text)
            if write:
                Path(write).expanduser().write_text(text, encoding="utf-8")
                typer.secho(f"\nWritten to {write}", fg="green")
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run: uv run alembic upgrade head", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


async def _history(container) -> list:
    """Every recorded validation run on this machine, newest first."""
    return await container.validation_runs.recent(limit=500)


async def _chosen(
    container, name: str, *, regression: bool, tag: str, phase: int
) -> list:
    """Which scenarios this invocation is about.

    The regression set is derived from history rather than declared: a scenario
    that has passed here has earned its place in it, and one that never has
    would only report the same failure every time. The file's own `regression`
    flag is the exception, for a fresh clone where nothing has passed yet.
    """
    registry = container.scenario_registry
    if name:
        return [registry.get(name)]

    chosen = registry.list_all()
    if tag:
        chosen = [scenario for scenario in chosen if tag in scenario.tags]
    if phase:
        chosen = [scenario for scenario in chosen if scenario.phase == phase]
    if regression:
        history = await _history(container)
        passed = {
            entry.scenario
            for entry in (reliability_of(s.name, history) for s in chosen)
            if entry.in_regression_set
        }
        chosen = [s for s in chosen if s.name in passed or s.regression]
    return chosen


_VERDICT_COLOURS = {
    Verdict.RELIABLE: "green",
    Verdict.SOMETIMES: "yellow",
    Verdict.NEVER: "red",
    Verdict.UNTRIED: "white",
    Verdict.UNAVAILABLE: "white",
}


def _report_validation(run) -> None:
    colour = {
        RunStatus.PASSED: "green",
        RunStatus.FAILED: "red",
        RunStatus.SKIPPED: "yellow",
    }[run.status]
    typer.secho(f"  [{run.status.value}]", fg=colour, nl=False)
    if run.failure is not FailureKind.NONE:
        typer.echo(f" {run.failure.value}", nl=False)
    metrics = run.metrics
    typer.echo(
        f"  {metrics.steps} step(s), ${metrics.cost_usd:.6f},"
        f" {metrics.duration_seconds:.0f}s,"
        f" {metrics.tool_calls} tool call(s)"
    )
    for check in run.checks:
        mark = "ok " if check.passed else "no "
        detail = f"  ({check.detail})" if check.detail and not check.passed else ""
        typer.echo(f"    {mark}{check.check}{detail}")
    if run.status is RunStatus.SKIPPED and run.summary:
        typer.echo(f"    {run.summary}")


def _resolve(approval_id: str, decision: ApprovalState, comment: str) -> None:
    async def _run() -> None:
        container = build_container()
        try:
            service = container.approval_service
            if service is None:
                typer.secho("Approvals are switched off in this configuration.", fg="red")
                raise typer.Exit(code=1)
            await service.resolve(UUID(approval_id), decision, comment=comment)
            typer.secho(f"{decision.value.lower()}: {approval_id}", fg="green")
        except ValueError as error:
            typer.secho(f"'{approval_id}' is not an approval id.", fg="red", err=True)
            raise typer.Exit(code=1) from error
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error
        finally:
            await container.aclose()

    asyncio.run(_run())


def _report_objective(result) -> None:
    from domain.workforce.protocols import ObjectiveStatus

    colour = {
        ObjectiveStatus.DONE: "green",
        ObjectiveStatus.FAILED: "red",
        ObjectiveStatus.ESCALATED: "yellow",
    }.get(result.status, "white")

    typer.echo(f"\n{result.summary}")
    if result.missing:
        typer.secho("\nStill missing:", fg="yellow")
        for item in result.missing:
            typer.echo(f"  - {item}")

    tasks = result.output.get("tasks") or []
    if tasks:
        # Who did what, so the answer can be checked rather than believed.
        typer.echo("")
        for task in tasks:
            typer.secho(f"  {task['employee']:<12}", fg="cyan", nl=False)
            typer.echo(f"{task['status']:<10} {task['goal'][:60]}")

    typer.secho(f"\n[{result.status.value}] {result.objective_id}", fg=colour)
    typer.echo(f"cost: ${result.cost_usd:.6f}")


def _report(task) -> None:
    from domain.tasks.task import TaskStatus

    colour = {
        TaskStatus.COMPLETED: "green",
        TaskStatus.FAILED: "red",
        TaskStatus.CANCELLED: "yellow",
    }.get(task.status, "white")

    if task.result and task.result.summary:
        typer.echo(f"\n{task.result.summary}")

    typer.secho(f"\n[{task.status}] {task.id}", fg=colour)
    if task.error:
        typer.secho(f"{task.error.kind}: {task.error.message}", fg="red")
    typer.echo(f"steps: {task.execution.step}  cost: ${task.cost_usd:.6f}")


if __name__ == "__main__":
    app()


# --- Work that starts on its own (§12.9) --------------------------------------


@app.command()
def schedules() -> None:
    """The standing instructions on this machine, and when each next fires.

    A schedule holds a request in the user's own words, the same sentence
    `ask-alethic` would take. It never names an employee: choosing one is the
    manager's job at the moment the work runs, not the user's months earlier.
    """

    async def _run() -> None:
        container = build_container()
        try:
            found = await container.schedule_repository.list()
            if not found:
                typer.echo(
                    "Nothing is scheduled here. Add one with "
                    '`alethic schedule "<request>" --every 3600`.'
                )
                return
            for schedule in found:
                state = "" if schedule.enabled else "  [paused]"
                typer.secho(schedule.name or str(schedule.id), fg="cyan", nl=False)
                typer.echo(f"  {schedule.describe()}{state}")
                typer.echo(f"  {schedule.request.splitlines()[0][:100]}")
                when = (
                    schedule.next_due_at.isoformat(timespec="minutes")
                    if schedule.next_due_at
                    else "when its event arrives"
                )
                typer.echo(f"  next: {when}   runs so far: {schedule.runs}")
        finally:
            await container.aclose()

    _guarded(_run)


@app.command()
def schedule(
    request: str = typer.Argument(..., help="What to ask Alethic for, in your own words."),
    name: str = typer.Option("", "--name", help="A short name, for reading the list."),
    every: int = typer.Option(0, "--every", help="Seconds between runs. Minimum 60."),
    daily_at: str = typer.Option("", "--daily-at", help="A time of day in UTC, HH:MM."),
    on_event: str = typer.Option("", "--on-event", help="An event kind to wait for."),
) -> None:
    """Ask for something to happen without being asked for again.

    Exactly one of `--every`, `--daily-at` and `--on-event`. A schedule that
    fired on two of them would fire twice for reasons a person reading the list
    could not separate.
    """
    from datetime import time as _time

    from domain.scheduling.models import Recurrence, Schedule

    chosen = [bool(every), bool(daily_at), bool(on_event)]
    if sum(chosen) != 1:
        typer.secho(
            "Choose exactly one of --every, --daily-at and --on-event.", fg="red", err=True
        )
        raise typer.Exit(code=1)

    async def _run() -> None:
        container = build_container()
        try:
            recurrence = None
            if every:
                recurrence = Recurrence(every_seconds=every)
            elif daily_at:
                recurrence = Recurrence(daily_at=_time.fromisoformat(daily_at))
            created = Schedule.create(
                request, name=name, recurrence=recurrence, on_event=on_event
            )
            await container.schedule_repository.save(created)
            typer.secho(f"Scheduled: {created.name or created.id}", fg="green")
            typer.echo(f"  {created.describe()}")
            typer.echo(
                "  It runs through the same manager, policies and approval gate as "
                "anything you ask for yourself - including the ones that stop for a "
                "person, which nobody will be there to answer."
            )
        finally:
            await container.aclose()

    _guarded(_run)


@app.command()
def unschedule(
    schedule_id: str = typer.Argument(..., help="The id from `alethic schedules`."),
    pause: bool = typer.Option(False, "--pause", help="Stop it without deleting it."),
) -> None:
    """Delete a schedule, or pause it and keep what it has done."""

    async def _run() -> None:
        container = build_container()
        try:
            store = container.schedule_repository
            found = await store.get(UUID(schedule_id))
            if found is None:
                typer.secho("No schedule with that id.", fg="red", err=True)
                raise typer.Exit(code=1)
            if pause:
                await store.save(found.set_enabled(False))
                typer.secho(f"Paused: {found.name or found.id}", fg="yellow")
            else:
                await store.delete(found.id)
                typer.secho(f"Deleted: {found.name or found.id}", fg="green")
        finally:
            await container.aclose()

    _guarded(_run)


@app.command()
def events(
    limit: int = typer.Option(20, "--limit", help="How many to show, newest first."),
) -> None:
    """What has happened here that work could be owed to."""

    async def _run() -> None:
        container = build_container()
        try:
            found = await container.event_log.recent(limit=limit)
            if not found:
                typer.echo("No events have been recorded here.")
                return
            for event in found:
                mark = "used" if event.consumed else "open"
                typer.secho(f"{mark}  {event.kind}", fg="cyan", nl=False)
                typer.echo(f"  {event.created_at.isoformat(timespec='seconds')}")
                if event.source:
                    typer.echo(f"      from {event.source}")
                if event.payload:
                    details = ", ".join(f"{k}={v}" for k, v in sorted(event.payload.items()))
                    typer.echo(f"      {details[:120]}")
        finally:
            await container.aclose()

    _guarded(_run)


def _guarded(coroutine_factory) -> None:
    """Run one CLI coroutine, reporting a platform error rather than a traceback."""

    async def _wrapped() -> None:
        try:
            await coroutine_factory()
        except StorageNotInitializedError as error:
            typer.secho(f"{error} Run `alembic upgrade head` first.", fg="red", err=True)
            raise typer.Exit(code=1) from error
        except AlethicError as error:
            typer.secho(f"{type(error).__name__}: {error}", fg="red", err=True)
            raise typer.Exit(code=1) from error

    asyncio.run(_wrapped())
