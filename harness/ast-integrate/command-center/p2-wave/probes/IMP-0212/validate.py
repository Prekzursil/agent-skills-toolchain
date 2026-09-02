"""Schema + static validation. Neither gate is a simulation; both must pass first."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ir import ALLOWED_TOOLS

try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

SCHEMA_PATH = Path(__file__).with_name("workflow_schema.json")
_SCHEMA: dict[str, Any] | None = None

SCHEMA_PATH = Path(__file__).with_name("workflow_schema.json")
_SCHEMA: dict[str, Any] | None = None


def load_schema() -> dict[str, Any]:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA


def schema_validate(wf: Any) -> tuple[bool, list[str]]:
    if not isinstance(wf, dict):
        return False, ["workflow must be an object"]
    schema = load_schema()
    if jsonschema is None:
        return _structural_schema(wf)
    errs = [
        f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
        for e in jsonschema.Draft7Validator(schema).iter_errors(wf)
    ]
    return (not errs, errs)


def _structural_schema(wf: dict[str, Any]) -> tuple[bool, list[str]]:
    """Fail-closed fallback if jsonschema is absent. Mirrors the required/enum rules."""
    errs: list[str] = []
    allowed_root = {
        "id",
        "kind",
        "goal",
        "stages",
        "stopping",
        "initial_inputs",
        "lineage",
    }
    extra = set(wf) - allowed_root
    if extra:
        errs.append(f"additionalProperties: {sorted(extra)}")
    for key in ("id", "kind", "stages", "stopping"):
        if key not in wf:
            errs.append(f"missing {key}")
    if wf.get("kind") != "workflow":
        errs.append("kind must be workflow")
    if not isinstance(wf.get("id"), str) or not wf.get("id"):
        errs.append("id must be a non-empty string")
    stages = wf.get("stages")
    if not isinstance(stages, list) or not stages:
        errs.append("stages must be a non-empty array")
        return False, errs
    stop = wf.get("stopping")
    if not isinstance(stop, dict):
        errs.append("stopping must be an object")
    else:
        if not isinstance(stop.get("max_stages"), int) or stop["max_stages"] < 1:
            errs.append("stopping.max_stages must be int >= 1")
        if stop.get("on_error") not in {"halt", "continue"}:
            errs.append("stopping.on_error must be halt|continue")
        if set(stop) - {"max_stages", "on_error"}:
            errs.append("stopping additionalProperties")
    kinds = {
        "static-scan",
        "write-config",
        "transform",
        "gate",
        "splice",
        "compose",
        "emulate",
        "emit",
    }
    for i, st in enumerate(stages):
        if not isinstance(st, dict):
            errs.append(f"stages[{i}] not an object")
            continue
        for key in (
            "id",
            "kind",
            "inputs",
            "outputs",
            "tool",
            "capability",
            "timeout_seconds",
        ):
            if key not in st:
                errs.append(f"stages[{i}] missing {key}")
        if st.get("kind") not in kinds:
            errs.append(f"stages[{i}] unknown kind")
        if not isinstance(st.get("timeout_seconds"), int) or st["timeout_seconds"] < 1:
            errs.append(f"stages[{i}] timeout_seconds must be int >= 1")
    return (not errs, errs)


def topo_stages(wf: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, list[str]]:
    stages = list(wf.get("stages") or [])
    produced = set(wf.get("initial_inputs") or [])
    remaining = list(stages)
    ordered: list[dict[str, Any]] = []
    while remaining:
        ready = [s for s in remaining if set(s.get("inputs") or []) <= produced]
        if not ready:
            missing = []
            for s in remaining:
                miss = sorted(set(s.get("inputs") or []) - produced)
                missing.append(f"{s.get('id')}: missing {miss}")
            return None, ["CYCLE_OR_UNSATISFIED_INPUTS: " + "; ".join(missing)]
        for s in ready:
            ordered.append(s)
            produced |= set(s.get("outputs") or [])
            remaining.remove(s)
    return ordered, []


def static_validate(wf: dict[str, Any]) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not isinstance(wf, dict):
        return False, ["workflow must be an object"]
    stages = wf.get("stages")
    if not isinstance(stages, list) or not stages:
        return False, ["stages must be a non-empty array"]
    ids = [s.get("id") for s in stages if isinstance(s, dict)]
    if len(ids) != len(set(ids)):
        errs.append("DUPLICATE_STAGE_ID")
    stop = wf.get("stopping") if isinstance(wf.get("stopping"), dict) else {}
    max_stages = stop.get("max_stages")
    if isinstance(max_stages, int) and max_stages < len(stages):
        errs.append("STOPPING_MAX_STAGES_LT_STAGE_COUNT")
    initial = wf.get("initial_inputs")
    if not isinstance(initial, list) or not initial:
        errs.append("MISSING_INITIAL_INPUTS")
    for i, st in enumerate(stages):
        if not isinstance(st, dict):
            continue
        tool = st.get("tool")
        if tool not in ALLOWED_TOOLS:
            errs.append(f"stages[{i}] UNDECLARED_TOOL:{tool}")
        timeout = st.get("timeout_seconds")
        if not isinstance(timeout, int) or timeout < 1:
            errs.append(f"stages[{i}] NONPOSITIVE_TIMEOUT")
        if not st.get("inputs"):
            errs.append(f"stages[{i}] EMPTY_INPUTS")
        if not st.get("outputs"):
            errs.append(f"stages[{i}] EMPTY_OUTPUTS")
    ordered, topo_errs = topo_stages(wf)
    errs.extend(topo_errs)
    if ordered is None:
        return False, errs
    return (not errs, errs)
