"""A mechanical scanner for RIVAL declarations of names agentspec already owns.

Prose promising "we reuse agentspec" is not a gate. This walks agentrail's own AST and reports
any module-level rebinding of an agentspec-owned constant or any class that redeclares an
agentspec-owned type. ``tests/test_no_rival_core.py`` requires the report to be EMPTY, and
``tests/test_mutations.py`` injects a rival declaration and requires it to be non-empty -- so the
scanner is proven in both states rather than trusted for its silence.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

OWNED_CONSTANTS: frozenset[str] = frozenset(
    {
        "WINDOWS_CMDLINE_CAP",
        "PROMPT_TRANSPORTS",
        "MIN_SUBSTRING_SCAN_LEN",
        "REASONS",
        "CLAUSES",
        "ENVELOPE_FIELDS",
        "STATUSES",
        "RECEIPT_FORMATS",
        "RETRYABLE_ONCE",
        "RATE_LIMIT_MAX_ATTEMPTS",
        "RATE_LIMIT_BASE_BACKOFF_MS",
        "DISPATCH_VIOLATIONS",
        "VIOLATIONS",
        "TERMINAL_RE",
        "BACKGROUND_PHRASES",
        "PROGRESS_LINE_RE",
    }
)
"""Constants that live in agentspec. Rebinding one at agentrail module level is a fork."""

OWNED_TYPES: frozenset[str] = frozenset(
    {
        "RailSpec",
        "ArgvPlan",
        "RailResult",
        "Verdict",
        "Observation",
        "ErrorDetail",
        "ReceiptSpec",
        "WorkUnit",
        "Workflow",
        "RetryDecision",
        "Clock",
    }
)
"""Types agentspec declares. A second class with the same name is a rival data model."""

OWNED_FUNCTIONS: frozenset[str] = frozenset(
    {
        "judge",
        "observe",
        "build_argv",
        "build_for_rail",
        "plan_retry",
        "check_dispatch",
        "terminal_line",
        "success_line",
        "failure_line",
        "validate_observation",
        "is_reason",
        "family",
        "rail_exit",
        "classify",
        "looks_like_progress",
    }
)
"""Functions agentspec owns. Re-defining one means the AND-gate/taxonomy logic was forked."""


@dataclass(frozen=True, slots=True)
class Rival:
    path: str
    line: int
    kind: str
    name: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line} redeclares {self.kind} {self.name!r}"


def rival_declarations(source: str, path: str) -> tuple[Rival, ...]:
    """Every rival declaration in ``source``. Empty means agentrail declared none."""
    tree = ast.parse(source, filename=path)
    found: list[Rival] = []
    for node in tree.body:
        found.extend(_from_node(node, path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name in OWNED_TYPES:
            found.append(Rival(path, node.lineno, "type", node.name))
        elif (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name in OWNED_FUNCTIONS
        ):
            found.append(Rival(path, node.lineno, "function", node.name))
    return tuple(sorted(set(found), key=lambda item: (item.path, item.line, item.name)))


def imported_names(source: str, path: str, module_prefix: str) -> frozenset[str]:
    """Names imported ``from <module_prefix>...`` -- proof a name is CONSUMED, not redeclared."""
    tree = ast.parse(source, filename=path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            module_prefix
        ):
            names.update(alias.name for alias in node.names)
    return frozenset(names)


def _from_node(node: ast.stmt, path: str) -> tuple[Rival, ...]:
    """Module-level constant rebinding only -- a local variable is not a fork."""
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]
    return tuple(
        Rival(path, node.lineno, "constant", target.id)
        for target in targets
        if isinstance(target, ast.Name) and target.id in OWNED_CONSTANTS
    )
