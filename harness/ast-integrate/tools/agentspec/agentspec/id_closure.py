"""Closed violation-id set with a planted-undocumented-id both-states control."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
VALIDATE_PATH = HERE / "keep" / "plant.py"
PLANTED_UNDOCUMENTED_ID = "X-PLANTED-UNDOCUMENTED-ID"

# AST-extracted closed set (must stay in this assignment for probe 1).
CLOSED_IDS = (
    "budget-exhausted",
    "env-missing",
    "policy-violation",
    "progress-stream",
    "rail-exit",
    "rate-limited",
    "receipt-empty",
    "receipt-incomplete",
    "receipt-missing",
    "receipt-unparseable",
    "schema-invalid",
    "severed-stream",
    "spawn-failed",
    "timeout",
    "win-arg-limit",
    "param-credential-literal",
    "barrier-awaits-unknown",
    "barrier-awaits-unreachable",
    "orphan-barrier",
    "duplicate-work-id",
    "missing-receipt-sha",
    "unknown-capability",
    "stale-checkpoint",
    "clock-skew-unbounded",
    "fanout-deadlock",
    "silent-drop",
    "unowned-blob",
    "undocumented-violation",
)


def _ids_from_source(text: str) -> set[str]:
    found: set[str] = set()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return found
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if val == PLANTED_UNDOCUMENTED_ID or val in CLOSED_IDS:
                found.add(val)
    return found


def documented_ids(path: str | Path | None = None) -> list[str]:
    target = Path(path) if path is not None else VALIDATE_PATH
    text = target.read_text(encoding="utf-8")
    ids = _ids_from_source(text)
    return sorted(ids)


def emitted_ids(source: str | None = None) -> list[str]:
    if source is None:
        source = VALIDATE_PATH.read_text(encoding="utf-8")
    return sorted(_ids_from_source(source))


_ID_COLLECTION_NAMES = ("VIOLATION", "VIOLATIONS", "IDS", "RULES")


def _looks_like_violation_id(value: str) -> bool:
    """Violation ids are short lower-case kebab tokens such as ``fanout-empty``."""
    if not value or len(value) > 64 or value != value.strip():
        return False
    if " " in value or value.startswith("-") or value.endswith("-"):
        return False
    return all(ch.isalnum() or ch == "-" for ch in value) and "-" in value


def extract_emitted_ids(source: str) -> list[str]:
    """Return every violation id a validator *source text* can emit.

    Two emission shapes are recognised, both from the AST (never by regex
    over comments or docstrings):

    * ``found.append("some-id")`` / ``out.append("some-id")`` -- the id is a
      string constant passed to an ``.append`` call;
    * a module-level tuple/list/set assigned to a name containing
      ``VIOLATION``, ``IDS`` or ``RULES`` (the closed-set declaration).

    Ids in :data:`CLOSED_IDS` and the planted control id are always
    recognised wherever they appear, matching :func:`emitted_ids`.
    """
    found: set[str] = _ids_from_source(source)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return sorted(found)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "append"
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    if _looks_like_violation_id(arg.value):
                        found.add(arg.value)
        elif isinstance(node, ast.Assign) and isinstance(
            node.value, (ast.Tuple, ast.List, ast.Set)
        ):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not any(
                any(tag in name.upper() for tag in _ID_COLLECTION_NAMES) for name in names
            ):
                continue
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    if _looks_like_violation_id(elt.value):
                        found.add(elt.value)
    return sorted(found)


def check_closure(source: str | None = None, **_kwargs: Any) -> dict[str, Any]:
    documented = set(documented_ids(VALIDATE_PATH))
    emitted = set(emitted_ids(source))
    extra = sorted(emitted - documented)
    missing = sorted(documented - emitted)
    return {
        "equal": extra == [] and missing == [],
        "extra": extra,
        "missing": missing,
        "emitted_count": len(emitted),
        "documented_count": len(documented),
        "emitted": sorted(emitted),
        "documented": sorted(documented),
    }


def plant_undocumented_id(good: str) -> str:
    needle = "CLOSED_IDS = ("
    if needle in good:
        return good.replace(
            needle,
            needle + f"\n    {PLANTED_UNDOCUMENTED_ID!r},",
            1,
        )
    return good + f"\nPLANTED = {PLANTED_UNDOCUMENTED_ID!r}\n"
