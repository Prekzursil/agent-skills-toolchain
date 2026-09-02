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
