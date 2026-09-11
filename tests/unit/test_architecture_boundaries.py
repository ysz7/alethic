"""The architecture rules, checked as tests rather than trusted as convention.

import-linter enforces the same contracts in CI; these tests fail faster and
say plainly what broke.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_IN_DOMAIN = {
    "app",
    "application",
    "infrastructure",
    "sqlalchemy",
    "alembic",
    "httpx",
    "openai",
    "anthropic",
    "playwright",
    "typer",
    "structlog",
    "pydantic_settings",
}

FORBIDDEN_IN_PROMETHEUS = {"infrastructure", "app", "employees"}


def imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def python_files(package: str) -> list[Path]:
    return sorted((REPO_ROOT / package).rglob("*.py"))


def test_domain_imports_nothing_but_the_standard_library() -> None:
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(imported_roots(path) & FORBIDDEN_IN_DOMAIN)
        for path in python_files("domain")
    }
    offenders = {path: roots for path, roots in offenders.items() if roots}
    assert not offenders, f"domain must not depend on infrastructure: {offenders}"


def test_application_does_not_import_infrastructure() -> None:
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(
            imported_roots(path) & {"infrastructure", "app"}
        )
        for path in python_files("application")
    }
    offenders = {path: roots for path, roots in offenders.items() if roots}
    assert not offenders, f"application talks to domain contracts only: {offenders}"


def test_prometheus_never_imports_a_concrete_employee_or_adapter() -> None:
    prometheus_dir = REPO_ROOT / "application" / "prometheus"
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(imported_roots(path) & FORBIDDEN_IN_PROMETHEUS)
        for path in sorted(prometheus_dir.rglob("*.py"))
    }
    offenders = {path: roots for path, roots in offenders.items() if roots}
    assert not offenders, f"Prometheus knows employees only through the registry: {offenders}"


def test_sql_does_not_leave_the_persistence_package() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for package in ("domain", "application", "app")
        for path in python_files(package)
        if "sqlalchemy" in imported_roots(path)
    ]
    assert not offenders, f"SQL must stay inside infrastructure/persistence: {offenders}"


def test_the_boundary_check_would_actually_catch_a_violation(tmp_path) -> None:
    """Guard the guard: a checker that never fails proves nothing."""
    offender = tmp_path / "leaky.py"
    offender.write_text("import httpx\nfrom sqlalchemy import select\n", encoding="utf-8")

    assert imported_roots(offender) & FORBIDDEN_IN_DOMAIN == {"httpx", "sqlalchemy"}


VENDOR_NAMES = (
    "openai",
    "anthropic",
    "claude",
    "gpt",
    "gemini",
    "openrouter",
    "mistral",
    "llama",
    "ollama",
    "playwright",
)


def test_no_vendor_is_named_anywhere_in_the_domain() -> None:
    """Phase 2 DoD: the domain describes capabilities, never products.

    The moment a vendor name appears in `domain/`, swapping providers stops
    being a configuration change.
    """
    offenders: dict[str, list[str]] = {}
    for path in python_files("domain"):
        text = path.read_text(encoding="utf-8").lower()
        found = sorted(name for name in VENDOR_NAMES if name in text)
        if found:
            offenders[str(path.relative_to(REPO_ROOT))] = found
    assert not offenders, f"vendor names leaked into the domain: {offenders}"


def test_the_interface_boundary_owns_no_transport() -> None:
    """Phase 13: `application/interface/` is a boundary, not a server.

    The moment it imports FastAPI, a socket or a template engine, a second
    interface stops being an adapter and starts being a fork - and the surface
    that got there first is the one every other one has to imitate.
    """
    transport = {"fastapi", "starlette", "uvicorn", "socket", "http", "websockets"}
    offenders = {
        str(path.relative_to(REPO_ROOT)): sorted(imported_roots(path) & transport)
        for path in sorted((REPO_ROOT / "application" / "interface").rglob("*.py"))
    }
    offenders = {path: roots for path, roots in offenders.items() if roots}
    assert not offenders, f"the interface boundary must not know a transport: {offenders}"


def test_the_http_adapter_reaches_the_platform_only_through_the_boundary() -> None:
    """`app/ui/` is transport. Everything it shows comes from `PrometheusService`.

    Checked by what it may reach for: the composition root, its own settings,
    the boundary's own types, and the confirmer it must construct because who
    answers an approval is a property of the interface. A repository, the
    manager or the runtime appearing here would be a route that had started
    deciding something, and the desktop shell would have no way to reach it.
    """
    allowed = {
        "application.interface",
        "application.scheduling",
        "app.config",
        "app.ui",
        "domain.errors",
        # Value types, on the same footing as the errors: a route has to be able
        # to say which workspace a request belongs to, and turning a path
        # segment into one is transport work. Neither module holds a rule, which
        # is what makes it safe to name here.
        "domain.workspace",
        "infrastructure.approvals",
        "infrastructure.container",
    }
    offenders: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "app" / "ui").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        reached = sorted(
            {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
                and node.module.split(".")[0]
                in {"application", "domain", "infrastructure", "app"}
                and not any(
                    node.module == prefix or node.module.startswith(prefix + ".")
                    for prefix in allowed
                )
            }
        )
        if reached:
            offenders[str(path.relative_to(REPO_ROOT))] = reached
    assert not offenders, f"the HTTP adapter must go through PrometheusService: {offenders}"


def test_nothing_above_the_tool_boundary_knows_what_mcp_is() -> None:
    """Phase 14: MCP is an extension mechanism, not part of the architecture.

    The rule ADR 0015 rests on. `domain/`, `application/` and the employee
    declarations ask for a capability and get a `Tool`; the protocol, its
    transport and the lifetime of a server live in `infrastructure/mcp/`, and
    `app/config/container.py` is the one place allowed to wire the two together
    - the composition root, exactly as it is for the screen reader.

    If this ever fails, the planner has grown a branch for where a tool came
    from, which is the thing the whole phase exists to prevent.
    """
    allowed = {
        REPO_ROOT / "app" / "config" / "container.py",
        REPO_ROOT / "infrastructure" / "mcp",
        REPO_ROOT / "infrastructure" / "tools" / "mcp.py",
    }
    offenders: dict[str, list[str]] = {}
    for package in ("domain", "application", "app"):
        for path in python_files(package):
            if any(path == entry or entry in path.parents for entry in allowed):
                continue
            text = path.read_text(encoding="utf-8")
            found = sorted(
                {line.strip() for line in text.splitlines() if "infrastructure.mcp" in line}
            )
            if found:
                offenders[str(path.relative_to(REPO_ROOT))] = found
    assert not offenders, f"MCP leaked above the tool boundary: {offenders}"


def test_an_integration_is_reached_through_the_same_registry_as_every_tool() -> None:
    """There is one tool system, and a discovered tool is in it.

    Asserted by absence: no second registry, no second executor, no parallel
    contract. A file whose name says otherwise is the first sign that the
    answer to "how does a tool run" has become two answers.
    """
    forbidden = {"MCPToolRegistry", "MCPExecutor", "MCPTaskExecutor", "IntegrationRegistry"}
    offenders: dict[str, list[str]] = {}
    for package in ("domain", "application", "infrastructure", "app"):
        for path in python_files(package):
            text = path.read_text(encoding="utf-8")
            found = sorted(name for name in forbidden if f"class {name}" in text)
            if found:
                offenders[str(path.relative_to(REPO_ROOT))] = found
    assert not offenders, f"a second tool system appeared: {offenders}"
