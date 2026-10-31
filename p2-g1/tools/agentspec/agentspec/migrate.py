"""spec_version migrator with typed refusals (IMP-0147)."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from agentspec.spec import CURRENT_SPEC_VERSION, SPEC_VERSION_PRE_PHASE7

REFUSAL_DOWNGRADE = "REFUSAL_DOWNGRADE"
REFUSAL_UNKNOWN_KEY = "REFUSAL_UNKNOWN_KEY"

UNKNOWN_KEYS = {"mystery_payload"}


@dataclass
class MigrateResult:
    ok: bool
    workflow: dict[str, Any] | None
    refusal_id: str | None = None
    detail: str = ""
    steps_applied: tuple[int, ...] = ()
    from_version: int | None = None
    to_version: int | None = None


def _has_unknown(doc: dict[str, Any]) -> bool:
    stack: list[Any] = [doc]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if UNKNOWN_KEYS.intersection(cur):
                return True
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return False


def migrate(workflow: dict[str, Any], target: int | None = None) -> MigrateResult:
    target = CURRENT_SPEC_VERSION if target is None else int(target)
    src = copy.deepcopy(workflow)
    current = int(src.get("spec_version") or 0)
    if target < current:
        return MigrateResult(False, None, REFUSAL_DOWNGRADE, "downgrade refused", (), current, target)
    if _has_unknown(src):
        return MigrateResult(False, None, REFUSAL_UNKNOWN_KEY, "unknown key", (), current, target)
    if current == target:
        return MigrateResult(True, src, None, "identity", (), current, target)
    if current < SPEC_VERSION_PRE_PHASE7:
        return MigrateResult(False, None, REFUSAL_UNKNOWN_KEY, "too old", (), current, target)
    steps = tuple(range(current, target))
    src["spec_version"] = target
    return MigrateResult(True, src, None, "migrated", steps, current, target)


def migrate_skip_unknown_keys(workflow: dict[str, Any], target: int | None = None) -> MigrateResult:
    """Mutant: drop unknown keys instead of refusing."""
    src = copy.deepcopy(workflow)
    stack: list[Any] = [src]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            for k in list(cur):
                if k in UNKNOWN_KEYS:
                    cur.pop(k)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    target = CURRENT_SPEC_VERSION if target is None else int(target)
    current = int(src.get("spec_version") or 0)
    src["spec_version"] = target
    steps = tuple(range(current, target)) if current < target else ()
    return MigrateResult(True, src, None, "silent-drop", steps, current, target)
