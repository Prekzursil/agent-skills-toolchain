"""Lint: every zero-duplicates verdict must carry adjacent machine-readable scope.

Adjacent means a `scope` key on the SAME JSON object as the zero-duplicates
field. A scope parked under limitations/caveats/notes does not count.
Machine-readable means a dict with methods[] and does_not_detect[] (each miss
names id + settling_experiment), or a WFA-SCOPE: token string. Prose fails.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterator

BOOL_KEYS = (
    "zero_duplicates",
    "zero-duplicates",
    "no_duplicates",
    "no-duplicates",
)
NO_DUP_VERDICTS = frozenset(
    {"NO-DUPLICATES", "ZERO-DUPLICATES", "NONE-FOUND", "CLEAN"}
)
TOKEN_SCOPE = re.compile(
    r"^WFA-SCOPE:[A-Za-z0-9+._-]+(;misses=[A-Za-z0-9,_-]+)?$"
)


def walk_dicts(obj: Any, path: str = "$") -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(obj, dict):
        yield path, obj
        for k, v in obj.items():
            yield from walk_dicts(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_dicts(v, f"{path}[{i}]")


def is_zero_duplicates_verdict(obj: dict[str, Any]) -> bool:
    for key in BOOL_KEYS:
        if obj.get(key) is True:
            return True
    verdict = str(obj.get("verdict") or "").upper().replace("_", "-")
    return verdict in NO_DUP_VERDICTS


def _miss_ok(item: Any) -> tuple[bool, str]:
    if isinstance(item, dict):
        cid = str(item.get("id") or "").strip()
        exp = str(
            item.get("settling_experiment")
            or item.get("settling_experiment_named")
            or ""
        ).strip()
        if not cid:
            return False, "does_not_detect.id-absent"
        if len(exp) < 16:
            return False, "does_not_detect.settling_experiment-absent"
        return True, "ok"
    if isinstance(item, str) and item.strip():
        return False, "does_not_detect-entry-not-object"
    return False, "does_not_detect-entry-empty"


def scope_machine_readable(scope: Any) -> tuple[bool, str]:
    if isinstance(scope, str):
        if TOKEN_SCOPE.fullmatch(scope.strip()):
            return True, "ok-token"
        return False, "scope-prose-not-machine-readable"
    if not isinstance(scope, dict):
        return False, "scope-wrong-type"
    methods = scope.get("methods")
    misses = scope.get("does_not_detect")
    if not isinstance(methods, list) or not methods:
        return False, "scope.methods-missing"
    if not all(isinstance(m, str) and m.strip() for m in methods):
        return False, "scope.methods-not-strings"
    if not isinstance(misses, list) or not misses:
        return False, "scope.does_not_detect-missing"
    for item in misses:
        ok, reason = _miss_ok(item)
        if not ok:
            return False, reason
    return True, "ok"


def verdict_scope_ok(obj: dict[str, Any]) -> tuple[bool, str]:
    if "scope" not in obj:
        return False, "scope-absent-not-adjacent"
    return scope_machine_readable(obj.get("scope"))


def lint_obj(doc: Any) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    seen = 0
    if not isinstance(doc, (dict, list)):
        return {
            "ok": False,
            "verdicts_seen": 0,
            "findings": [
                {"json_path": "$", "reason": "doc-not-object-or-array", "id": None}
            ],
        }
    for path, obj in walk_dicts(doc):
        if not is_zero_duplicates_verdict(obj):
            continue
        seen += 1
        ok, reason = verdict_scope_ok(obj)
        if not ok:
            findings.append(
                {
                    "json_path": path,
                    "reason": reason,
                    "id": obj.get("id"),
                }
            )
    return {
        "ok": seen > 0 and not findings,
        "verdicts_seen": seen,
        "findings": findings,
    }


def lint_path(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "verdicts_seen": 0,
            "findings": [
                {
                    "json_path": "$",
                    "reason": f"unparseable:{type(exc).__name__}",
                    "id": None,
                }
            ],
            "path": str(path),
        }
    result = lint_obj(doc)
    result["path"] = str(path)
    return result
