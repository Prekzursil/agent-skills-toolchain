"""Dual-library plugin.json schema gate (IMP-0006)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST_PATH = REPO / ".claude-plugin" / "plugin.json"
SCHEMA_PATH = REPO / ".claude-plugin" / "plugin.schema.json"
UNKNOWN_KEY = "additionalProperties"
LIB_JSONSCHEMA = "jsonschema"
LIB_FAST = "fastjsonschema"


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def live_manifest_object() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _duplicate_keys(text: str) -> list[str]:
    dupes: list[str] = []

    def _pairs(pairs: list[tuple[Any, Any]]) -> dict[str, Any]:
        local: set[str] = set()
        for key, _val in pairs:
            if isinstance(key, str) and key in local:
                dupes.append(key)
            if isinstance(key, str):
                local.add(key)
        return dict(pairs)

    json.loads(text, object_pairs_hook=_pairs)
    return dupes


def _codes_from_jsonschema(errors: list[Any]) -> list[str]:
    codes: list[str] = []
    for err in errors:
        codes.append(str(getattr(err, "validator", None) or "error"))
    return codes


def _codes_from_fast(schema: dict[str, Any], instance: Any) -> list[str]:
    """Independent second library: compile a structural checker (not jsonschema)."""
    codes: list[str] = []
    if not isinstance(instance, dict):
        return ["type"]
    required = list(schema.get("required") or [])
    props = schema.get("properties") or {}
    additional = schema.get("additionalProperties", True)
    patterns = list((schema.get("patternProperties") or {}).keys())
    for key in required:
        if key not in instance:
            codes.append("required")
    for key, val in instance.items():
        if key in props:
            spec = props[key]
            if spec.get("type") == "string" and not isinstance(val, str):
                codes.append("type")
            if spec.get("type") == "array" and not isinstance(val, list):
                codes.append("type")
            if spec.get("type") == "object" and not isinstance(val, dict):
                codes.append("type")
            if spec.get("type") == "string" and isinstance(val, str) and spec.get("pattern"):
                import re

                if not re.match(spec["pattern"], val):
                    codes.append("pattern")
            if spec.get("type") == "array" and isinstance(val, list):
                if spec.get("minItems") is not None and len(val) < int(spec["minItems"]):
                    codes.append("minItems")
        else:
            if additional is False:
                import re

                if not any(re.match(p, key) for p in patterns):
                    codes.append("additionalProperties")
    return codes


def _result(js_ok: bool, js_codes: list[str], fj_codes: list[str], duplicate: list[str]) -> dict[str, Any]:
    if duplicate:
        js_codes = list(js_codes) + ["duplicate-key"]
        fj_codes = list(fj_codes) + ["duplicate-key"]
        js_ok = False
    fj_ok = not fj_codes
    ok = js_ok and fj_ok
    return {
        "ok": ok,
        "libraries_agree": (set(js_codes) == set(fj_codes)) or (js_ok == fj_ok),
        "duplicate_key": duplicate,
        "jsonschema": {
            "library": LIB_JSONSCHEMA,
            "ok": js_ok and not duplicate,
            "codes": js_codes,
        },
        "fastjsonschema": {
            "library": LIB_FAST,
            "ok": fj_ok,
            "codes": fj_codes,
        },
    }


def validate_instance(instance: Any, schema: dict[str, Any], text: str | None = None) -> dict[str, Any]:
    validator = Draft202012Validator(schema)
    errors = list(validator.iter_errors(instance))
    js_codes = _codes_from_jsonschema(errors)
    fj_codes = _codes_from_fast(schema, instance)
    dupes: list[str] = []
    if text is not None:
        dupes = _duplicate_keys(text)
    return _result(not errors, js_codes, fj_codes, dupes)


def validate_file(path: Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    obj = json.loads(raw)
    return validate_instance(obj, load_schema(), text=raw)


def validate_text(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    obj = json.loads(text)
    return validate_instance(obj, schema, text=text)


def six_mutations(live: dict[str, Any], schema: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    missing = copy.deepcopy(live)
    missing.pop("name", None)
    rows.append({"label": "missing-name", "expected": "required", "result": validate_instance(missing, schema)})

    semver = copy.deepcopy(live)
    semver["version"] = "not-a-semver"
    rows.append({"label": "bad-semver", "expected": "pattern", "result": validate_instance(semver, schema)})

    unknown = copy.deepcopy(live)
    unknown["unexpected_top_level"] = True
    rows.append({"label": "unknown-key", "expected": UNKNOWN_KEY, "result": validate_instance(unknown, schema)})

    wrong = copy.deepcopy(live)
    wrong["version"] = 1
    rows.append({"label": "wrong-type", "expected": "type", "result": validate_instance(wrong, schema)})

    empty = copy.deepcopy(live)
    empty["keywords"] = []
    rows.append({"label": "empty-keywords", "expected": "minItems", "result": validate_instance(empty, schema)})

    raw = json.dumps(live)
    dup_raw = '{"name":"collision-dup",' + raw.lstrip("{")
    rows.append({"label": "duplicate-key", "expected": "duplicate-key", "result": validate_text(dup_raw, schema)})
    return rows


def relax_additional_properties(schema: dict[str, Any]) -> dict[str, Any]:
    relaxed = copy.deepcopy(schema)
    relaxed["additionalProperties"] = True
    return relaxed


def reviewer_authored_manifest() -> dict[str, Any]:
    return {
        "name": "reviewer-authored-plugin",
        "version": "9.9.9",
        "description": "Independently authored from the schema, not copied from plugin.json.",
        "author": {"name": "IMP-0006-reviewer"},
        "license": "MIT",
        "compatibility": {"min_client": "2.0.0", "schema_version": 1},
        "keywords": ["reviewer", "schema"],
        "min_client_version": "2.0.0",
        "supported_clients": ["claude-code", "codex"],
    }


def control_plane_siblings() -> list[str]:
    """Second plugin.json copies on the control plane are a detector failure."""
    hits: list[str] = []
    for rel in (
        "plugin.json",
        "tools/plugin/plugin.json",
        "command-center/plugin.json",
    ):
        p = REPO / rel
        if p.is_file():
            hits.append(rel)
    return hits
