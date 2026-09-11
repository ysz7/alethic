"""Loads workflow declarations from `workflows/*.yaml`.

The employee registry's rule, applied to the other kind of declaration: adding a
workflow is adding a file, and if it ever requires touching a Python file, this
is the one that would have to change - which would be the bug.

Strict about shape and specific about the file, for the same reason: a workflow
is written by hand and read by nobody until a run goes wrong. `step` instead of
`steps`, a dependency on a step that was renamed, or `max_attempts: 0` would all
otherwise show up as a run that quietly did less than the author intended.

What it does not check is the machine: whether the employees a workflow names
are declared here is a question for the employee registry, and `prometheus workflows`
asks it there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from domain.errors import ConfigurationError, NotFoundError
from domain.workflows.definition import (
    OnFailure,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTrigger,
)
from infrastructure.observability.logging import get_logger

log = get_logger(__name__)

DEFAULT_WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "workflows"

KNOWN_FIELDS = frozenset({"name", "description", "trigger", "steps", "inputs"})
KNOWN_STEP_FIELDS = frozenset(
    {"name", "employee", "instruction", "depends_on", "max_attempts", "on_failure"}
)


class YamlWorkflowRegistry:
    """Implements `domain.workflows.protocols.WorkflowRegistry`."""

    def __init__(self, directory: Path | None = None) -> None:
        self._directory = directory or DEFAULT_WORKFLOWS_DIR
        self._loaded: dict[str, WorkflowDefinition] | None = None

    @property
    def directory(self) -> Path:
        return self._directory

    def list_all(self) -> list[WorkflowDefinition]:
        return sorted(self._all().values(), key=lambda definition: definition.name)

    def get(self, name: str) -> WorkflowDefinition:
        definition = self._all().get(name)
        if definition is None:
            known = ", ".join(sorted(self._all())) or "none"
            raise NotFoundError(f"Unknown workflow: {name}. Declared here: {known}.")
        return definition

    def reload(self) -> None:
        self._loaded = None

    def _all(self) -> dict[str, WorkflowDefinition]:
        if self._loaded is None:
            self._loaded = self._discover()
        return self._loaded

    def _discover(self) -> dict[str, WorkflowDefinition]:
        if not self._directory.is_dir():
            return {}
        found: dict[str, WorkflowDefinition] = {}
        for path in sorted(self._directory.glob("*.yaml")):
            definition = _load(path)
            if definition.name in found:
                raise ConfigurationError(
                    f"{path}: a workflow named '{definition.name}' is already declared."
                )
            found[definition.name] = definition
        log.info("workflows.loaded", count=len(found), directory=str(self._directory))
        return found


def _load(path: Path) -> WorkflowDefinition:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as error:
        raise ConfigurationError(f"{path}: not valid YAML - {error}") from error
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{path}: expected a mapping at the top level.")

    unknown = sorted(set(raw) - KNOWN_FIELDS)
    if unknown:
        raise ConfigurationError(
            f"{path}: unknown field(s) {', '.join(unknown)}. "
            f"Known fields: {', '.join(sorted(KNOWN_FIELDS))}."
        )

    name = str(raw.get("name", "") or "").strip()
    # The file name is the identity, exactly as the directory name is for an
    # employee - so two workflows with one name are impossible rather than
    # resolved by load order.
    if name != path.stem:
        raise ConfigurationError(
            f"{path}: name is '{name}' but the file is '{path.stem}.yaml'. They must match."
        )

    trigger = str(raw.get("trigger", WorkflowTrigger.MANUAL.value)).upper()
    if trigger not in {member.value for member in WorkflowTrigger}:
        raise ConfigurationError(
            f"{path}: trigger '{trigger}' is not one of "
            f"{', '.join(member.value for member in WorkflowTrigger)}."
        )

    steps = raw.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise ConfigurationError(f"{path}: a workflow needs at least one step.")

    return WorkflowDefinition(
        name=name,
        description=str(raw.get("description", "") or "").strip(),
        trigger=WorkflowTrigger(trigger),
        steps=tuple(_step(path, index, entry) for index, entry in enumerate(steps)),
        inputs=dict(raw.get("inputs") or {}),
    )


def _step(path: Path, index: int, raw: Any) -> WorkflowStep:
    where = f"{path}: step {index + 1}"
    if not isinstance(raw, dict):
        raise ConfigurationError(f"{where}: expected a mapping.")

    unknown = sorted(set(raw) - KNOWN_STEP_FIELDS)
    if unknown:
        raise ConfigurationError(
            f"{where}: unknown field(s) {', '.join(unknown)}. "
            f"Known fields: {', '.join(sorted(KNOWN_STEP_FIELDS))}."
        )

    for required in ("name", "employee", "instruction"):
        if not str(raw.get(required, "") or "").strip():
            raise ConfigurationError(f"{where}: '{required}' is required and must have text.")

    attempts = raw.get("max_attempts", 1)
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 1:
        raise ConfigurationError(f"{where}: max_attempts must be a whole number of 1 or more.")

    on_failure = str(raw.get("on_failure", OnFailure.STOP.value)).upper()
    if on_failure not in {member.value for member in OnFailure}:
        raise ConfigurationError(
            f"{where}: on_failure '{on_failure}' is not one of "
            f"{', '.join(member.value for member in OnFailure)}."
        )

    depends_on = raw.get("depends_on") or []
    if isinstance(depends_on, str):
        depends_on = [depends_on]
    if not isinstance(depends_on, list):
        raise ConfigurationError(f"{where}: depends_on must be a list of step names.")

    return WorkflowStep(
        name=str(raw["name"]).strip(),
        employee=str(raw["employee"]).strip(),
        instruction=str(raw["instruction"]).strip(),
        depends_on=tuple(str(entry).strip() for entry in depends_on),
        max_attempts=attempts,
        on_failure=OnFailure(on_failure),
    )
