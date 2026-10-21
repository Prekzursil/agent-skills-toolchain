"""Static constructor extraction and live emit_records for ADV-0039."""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TELEMETRY_REL = "tools/router/telemetry.py"
TELEMETRY = REPO / TELEMETRY_REL
PHASE4_REL = "command-center/phase4/contracts/ARC-0096.json"
UNIT = "ADV-0039"
PERMITTED_CONTROL = "join_key"
FORBIDDEN_CONTROL = "prompt"
PLANTED_VALUE = "ADV-0039-PLANTED-FORBIDDEN"
MONTH = "2026-07"

EVENTS: list[dict[str, Any]] = [
    {
        "ts": "2026-07-02T12:00:00Z",
        "session_id": "sess-adv0039-a",
        "user_id": "user-a",
        "type": "router.offer",
        "capabilities": ["cap.lint", "cap.test"],
    },
    {
        "ts": "2026-07-02T12:01:00Z",
        "session_id": "sess-adv0039-a",
        "user_id": "user-a",
        "type": "router.use",
        "capabilities": ["cap.lint"],
    },
    {
        "ts": "2026-07-02T12:10:00Z",
        "session_id": "sess-adv0039-a",
        "user_id": "user-a",
        "type": "task.outcome",
        "outcome": "SUCCESS",
    },
]


def _tree() -> ast.AST:
    return ast.parse(TELEMETRY.read_text(encoding="utf-8"))


def _str_list_from_tuple(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.Tuple):
        return []
    out: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
    return out


def _str_list_from_set(node: ast.AST) -> list[str]:
    if not isinstance(node, ast.Set):
        return []
    out: list[str] = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            out.append(elt.value)
    return sorted(out)


def _assign_value(tree: ast.AST, name: str) -> ast.AST | None:
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return node.value
    return None


def recorded_fields(tree: ast.AST | None = None) -> list[str]:
    tree = tree or _tree()
    val = _assign_value(tree, "RECORDED_FIELDS")
    if val is None:
        raise RuntimeError("RECORDED_FIELDS missing")
    fields = _str_list_from_tuple(val)
    if PERMITTED_CONTROL not in fields:
        raise RuntimeError("allowlist missing permitted control field")
    return fields


def sensitive_fields(tree: ast.AST | None = None) -> list[str]:
    tree = tree or _tree()
    val = _assign_value(tree, "SENSITIVE_FIELDS")
    if val is None:
        raise RuntimeError("SENSITIVE_FIELDS missing")
    if isinstance(val, ast.Call) and val.args:
        fields = _str_list_from_set(val.args[0])
    else:
        fields = []
    if FORBIDDEN_CONTROL not in fields:
        raise RuntimeError("sensitive set missing forbidden control field")
    return fields


def emit_records_fn(tree: ast.AST | None = None) -> ast.FunctionDef:
    tree = tree or _tree()
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.FunctionDef) and node.name == "emit_records":
            return node
    raise RuntimeError("emit_records missing")


def constructor_keys(tree: ast.AST | None = None) -> dict[str, list[str]]:
    func = emit_records_fn(tree)
    production: list[str] = []
    test_only: list[str] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Dict):
            keys = [
                k.value
                for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            if PERMITTED_CONTROL in keys and "month" in keys:
                production = keys
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Subscript):
                    continue
                sl = target.slice
                if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    test_only.append(sl.value)
    if not production:
        raise RuntimeError("production constructor dict not found")
    return {
        "production_keys": sorted(set(production)),
        "test_only_keys": sorted(set(test_only)),
    }


def router_http_needles() -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    needles = ("urlopen", "http.client", "urllib.request", "requests.post")
    root = REPO / "tools" / "router"
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO).as_posix()
        for needle in needles:
            if needle in text:
                hits.append({"path": rel, "needle": needle})
    return hits


def static_extract() -> dict[str, Any]:
    tree = _tree()
    allow = recorded_fields(tree)
    forbidden = sensitive_fields(tree)
    ctor = constructor_keys(tree)
    prod = ctor["production_keys"]
    extra = sorted(set(prod) - set(allow))
    missing = sorted(set(allow) - set(prod))
    phase4 = REPO / PHASE4_REL
    return {
        "probe": "probe1-static-extract",
        "unit_id": UNIT,
        "module": TELEMETRY_REL,
        "recorded_fields": allow,
        "sensitive_fields": forbidden,
        "constructor_production_keys": prod,
        "constructor_test_only_keys": ctor["test_only_keys"],
        "extra_vs_allowlist": extra,
        "missing_vs_allowlist": missing,
        "permitted_control_in_constructor": PERMITTED_CONTROL in prod,
        "forbidden_control_in_constructor": FORBIDDEN_CONTROL in prod,
        "http_clients_in_router": router_http_needles(),
        "phase4_contract_path": PHASE4_REL,
        "phase4_contract_present": phase4.is_file(),
        "pass": True,
    }


def _router():
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    from router import telemetry as T  # noqa: WPS433

    return T


def live_records() -> list[dict[str, Any]]:
    T = _router()
    records = T.emit_records(EVENTS, REPO, month=MONTH)
    out: list[dict[str, Any]] = []
    for rec in records:
        item = json.loads(json.dumps(rec, default=str))
        if not isinstance(item, dict):
            raise RuntimeError("emit_records row is not an object")
        out.append(item)
    if not out:
        raise RuntimeError("emit_records returned no rows")
    return out


def live_key_union(records: list[dict[str, Any]] | None = None) -> list[str]:
    records = records if records is not None else live_records()
    keys: set[str] = set()
    for rec in records:
        keys.update(str(k) for k in rec.keys())
    return sorted(keys)
