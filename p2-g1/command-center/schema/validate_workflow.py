#!/usr/bin/env python3
"""Validate a catalog-class workflow against workflow.schema.json plus semantics.

Closed violation ids (CNF-0083 corpus):
  WF-UNKNOWN-STAGE-TYPE, WF-MISSING-STOP-RULE, WF-CYCLIC-SUBWORKFLOW,
  WF-UNDECLARED-TOOL, WF-NEGATIVE-TIMEOUT, WF-DUPLICATE-STAGE-ID

Cycle walks are bounded by MAX_CYCLE_DFS so a deep or cyclic subworkflow
graph cannot grow without an application stop (ADV-0034).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_PATH = Path(__file__).with_name("workflow.schema.json")
MAX_CYCLE_DFS = 64

WF_UNKNOWN_STAGE_TYPE = "WF-UNKNOWN-STAGE-TYPE"
WF_MISSING_STOP_RULE = "WF-MISSING-STOP-RULE"
WF_CYCLIC_SUBWORKFLOW = "WF-CYCLIC-SUBWORKFLOW"
WF_UNDECLARED_TOOL = "WF-UNDECLARED-TOOL"
WF_NEGATIVE_TIMEOUT = "WF-NEGATIVE-TIMEOUT"
WF_DUPLICATE_STAGE_ID = "WF-DUPLICATE-STAGE-ID"
WF_SCHEMA = "WF-SCHEMA"
WF_UNPARSEABLE = "WF-UNPARSEABLE"

KNOWN_STAGE_TYPES = frozenset(
    {
        "task",
        "subworkflow",
        "gate",
        "human",
        "loop",
        "fanout",
        "barrier",
        "checkpoint",
    }
)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _v(vid: str, detail: str) -> dict[str, str]:
    return {"id": vid, "detail": detail}


def _registry(root: dict[str, Any]) -> dict[str, dict[str, Any]]:
    reg: dict[str, dict[str, Any]] = {}

    def add(wf: dict[str, Any], key: str | None = None) -> None:
        if not isinstance(wf, dict):
            return
        wid = str(wf.get("id") or key or "")
        if wid:
            reg[wid] = wf
        if key and key not in reg:
            reg[str(key)] = wf
        subs = wf.get("subworkflows") or {}
        if isinstance(subs, dict):
            for sk, child in subs.items():
                add(child if isinstance(child, dict) else {}, str(sk))

    add(root)
    return reg


def _cycle_walk(root: dict[str, Any]) -> tuple[bool, int]:
    registry = _registry(root)
    calls = 0

    def dfs(wf_id: str, stack: frozenset[str]) -> bool:
        nonlocal calls
        calls += 1
        if calls > MAX_CYCLE_DFS:
            return True
        if wf_id in stack:
            return True
        wf = registry.get(wf_id)
        if not isinstance(wf, dict):
            return False
        nxt = stack | {wf_id}
        for stage in wf.get("stages") or []:
            if not isinstance(stage, dict):
                continue
            if str(stage.get("type") or "") != "subworkflow":
                continue
            target = str(stage.get("subworkflow") or "")
            if target and dfs(target, nxt):
                return True
        return False

    root_id = str(root.get("id") or "")
    cyclic = bool(root_id) and dfs(root_id, frozenset())
    return cyclic, calls


def _walk_workflows(root: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(wf: dict[str, Any]) -> None:
        ident = id(wf)
        if ident in seen or not isinstance(wf, dict):
            return
        seen.add(ident)
        out.append(wf)
        subs = wf.get("subworkflows") or {}
        if isinstance(subs, dict):
            for child in subs.values():
                if isinstance(child, dict):
                    add(child)

    add(root)
    return out


def semantic_validate(
    workflow: dict[str, Any],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Return (violations, extras). extras always includes cycle DFS counts."""
    violations: list[dict[str, str]] = []
    extras: dict[str, Any] = {
        "cycle_dfs_bound": MAX_CYCLE_DFS,
        "cycle_dfs_calls": 0,
    }
    if not isinstance(workflow, dict):
        return [_v(WF_SCHEMA, "workflow is not an object")], extras

    if not workflow.get("stop_rule"):
        violations.append(_v(WF_MISSING_STOP_RULE, "stop_rule is missing"))

    allow = {
        str(t) for t in (workflow.get("tools") or []) if isinstance(t, str)
    }

    for wf in _walk_workflows(workflow):
        wf_allow = {
            str(t) for t in (wf.get("tools") or []) if isinstance(t, str)
        } or allow
        timeout = wf.get("timeout_seconds")
        if isinstance(timeout, int) and not isinstance(timeout, bool) and timeout < 0:
            violations.append(
                _v(
                    WF_NEGATIVE_TIMEOUT,
                    f"workflow {wf.get('id')} timeout_seconds={timeout}",
                )
            )
        seen_ids: set[str] = set()
        for stage in wf.get("stages") or []:
            if not isinstance(stage, dict):
                continue
            sid = str(stage.get("id") or "")
            if sid:
                if sid in seen_ids:
                    violations.append(
                        _v(
                            WF_DUPLICATE_STAGE_ID,
                            f"duplicate stage id {sid} in {wf.get('id')}",
                        )
                    )
                seen_ids.add(sid)
            stype = str(stage.get("type") or "")
            if stype and stype not in KNOWN_STAGE_TYPES:
                violations.append(
                    _v(
                        WF_UNKNOWN_STAGE_TYPE,
                        f"stage {sid or '?'} has unknown type {stype}",
                    )
                )
            st_timeout = stage.get("timeout_seconds")
            if (
                isinstance(st_timeout, int)
                and not isinstance(st_timeout, bool)
                and st_timeout < 0
            ):
                violations.append(
                    _v(
                        WF_NEGATIVE_TIMEOUT,
                        f"stage {sid} timeout_seconds={st_timeout}",
                    )
                )
            for tool in stage.get("tools") or []:
                name = str(tool)
                if name and name not in wf_allow:
                    violations.append(
                        _v(
                            WF_UNDECLARED_TOOL,
                            f"stage {sid} uses undeclared tool {name}",
                        )
                    )

    cyclic, calls = _cycle_walk(workflow)
    extras["cycle_dfs_calls"] = calls
    if cyclic:
        violations.append(
            _v(
                WF_CYCLIC_SUBWORKFLOW,
                f"subworkflow graph is cyclic or exceeds MAX_CYCLE_DFS={MAX_CYCLE_DFS}",
            )
        )
    return violations, extras


def _schema_errors(document: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - environment
        return [f"schema-load:ImportError:{exc}"]
    try:
        schema = load_schema()
        return [
            e.message
            for e in jsonschema.Draft7Validator(schema).iter_errors(document)
        ]
    except Exception as exc:  # pragma: no cover - environment
        return [f"schema-load:{type(exc).__name__}:{exc}"]


def validate_document(document: dict[str, Any]) -> dict[str, Any]:
    semantic, extras = semantic_validate(document)
    schema_errs = _schema_errors(document) if isinstance(document, dict) else []
    first = semantic[0] if semantic else None
    if first is None and schema_errs:
        first = _v(WF_SCHEMA, schema_errs[0])
        semantic = [first]
    ok = not semantic
    return {
        "ok": ok,
        "violation_id": None if ok else first["id"],
        "detail": None if ok else first["detail"],
        "violations": semantic,
        "schema_errors": schema_errs,
        "cycle_dfs_calls": extras.get("cycle_dfs_calls"),
        "cycle_dfs_bound": extras.get("cycle_dfs_bound"),
    }


def validate_path(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
        doc = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "path": str(p),
            "violation_id": WF_UNPARSEABLE,
            "detail": f"{type(exc).__name__}:{exc}",
            "violations": [_v(WF_UNPARSEABLE, f"{type(exc).__name__}:{exc}")],
            "cycle_dfs_calls": 0,
            "cycle_dfs_bound": MAX_CYCLE_DFS,
        }
    result = validate_document(doc if isinstance(doc, dict) else {})
    result["path"] = str(p)
    return result


def format_error_line(result: dict[str, Any]) -> str:
    if result.get("ok"):
        return "OK"
    vid = str(result.get("violation_id") or WF_SCHEMA)
    detail = str(result.get("detail") or "")
    if detail:
        return f"{vid}: {detail}"
    return vid


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            json.dumps(
                {
                    "ok": False,
                    "violation_id": "WF-USAGE",
                    "detail": "validate_workflow.py <workflow.json>",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    result = validate_path(args[0])
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
