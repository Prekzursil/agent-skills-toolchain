#!/usr/bin/env python3
"""Measure real JSON consumers on duplicate-key and case-variant documents.

Behaviours are classified from the parsed result (last-wins, first-wins,
error, both-preserved, casefold-collapse). Nothing is assumed from a
language spec comment.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
DUP_PATH = FIXTURES / "planted-duplicate-keys.json"
CASE_PATH = FIXTURES / "planted-case-variant.json"

DUP_FIRST = "first"
DUP_LAST = "second"
DUP_KEY = "id"
CASE_FIRST_KEY = "Name"
CASE_FIRST_VAL = "alpha"
CASE_SECOND_KEY = "name"
CASE_SECOND_VAL = "beta"

INSTANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "Name": {"type": "string"},
        "name": {"type": "string"},
        "id": {"type": "string"},
    },
    "additionalProperties": False,
}


def _error(exc: BaseException) -> dict[str, Any]:
    return {
        "behaviour": "error",
        "error_type": type(exc).__name__,
        "message": str(exc)[:240],
        "assumed": False,
    }


def classify_duplicate(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {
            "behaviour": "error",
            "detail": f"not-object:{type(obj).__name__}",
            "assumed": False,
        }
    if DUP_KEY not in obj:
        return {"behaviour": "error", "detail": "key-absent", "assumed": False}
    val = obj[DUP_KEY]
    if val == DUP_LAST:
        behaviour = "last-wins"
    elif val == DUP_FIRST:
        behaviour = "first-wins"
    else:
        behaviour = "unexpected-value"
    return {
        "behaviour": behaviour,
        "observed_key": DUP_KEY,
        "observed_value": val,
        "first_value": DUP_FIRST,
        "last_value": DUP_LAST,
        "assumed": False,
    }


def classify_case_variant(obj: Any) -> dict[str, Any]:
    if not isinstance(obj, dict):
        return {
            "behaviour": "error",
            "detail": f"not-object:{type(obj).__name__}",
            "assumed": False,
        }
    has_first = CASE_FIRST_KEY in obj
    has_second = CASE_SECOND_KEY in obj
    fold_hits = [k for k in obj.keys() if str(k).casefold() == "name"]
    if has_first and has_second:
        return {
            "behaviour": "both-preserved",
            "keys_kept": [CASE_FIRST_KEY, CASE_SECOND_KEY],
            "values": {
                CASE_FIRST_KEY: obj[CASE_FIRST_KEY],
                CASE_SECOND_KEY: obj[CASE_SECOND_KEY],
            },
            "assumed": False,
        }
    if len(fold_hits) == 1:
        kept = fold_hits[0]
        val = obj[kept]
        if val == CASE_SECOND_VAL:
            resolution = "last-wins"
        elif val == CASE_FIRST_VAL:
            resolution = "first-wins"
        else:
            resolution = "collapsed-unknown-value"
        return {
            "behaviour": "casefold-collapse",
            "keys_kept": [kept],
            "observed_value": val,
            "resolution": resolution,
            "assumed": False,
        }
    if has_first and not has_second:
        return {
            "behaviour": "dropped-one",
            "keys_kept": [CASE_FIRST_KEY],
            "observed_value": obj[CASE_FIRST_KEY],
            "assumed": False,
        }
    if has_second and not has_first:
        return {
            "behaviour": "dropped-one",
            "keys_kept": [CASE_SECOND_KEY],
            "observed_value": obj[CASE_SECOND_KEY],
            "assumed": False,
        }
    return {
        "behaviour": "error",
        "detail": "neither-key-present",
        "keys_seen": [str(k) for k in obj.keys()],
        "assumed": False,
    }


def _from_mapping(obj: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    return classify_duplicate(obj), classify_case_variant(obj)


def python_loads(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return classify_duplicate(json.loads(dup)), classify_case_variant(json.loads(case))


def python_load_file(dup_path: Path, case_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    with dup_path.open(encoding="utf-8") as fh:
        dup_obj = json.load(fh)
    with case_path.open(encoding="utf-8") as fh:
        case_obj = json.load(fh)
    return classify_duplicate(dup_obj), classify_case_variant(case_obj)


def python_decoder(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    dec = json.JSONDecoder()
    return classify_duplicate(dec.decode(dup)), classify_case_variant(dec.decode(case))


def reject_duplicate_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key: {key}")
        seen.add(key)
        out[key] = value
    return out


def casefold_last_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        out[str(key).casefold()] = value
    return out


def python_strict_dup(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        dup_obj = json.loads(dup, object_pairs_hook=reject_duplicate_hook)
        dup_row = classify_duplicate(dup_obj)
    except (ValueError, json.JSONDecodeError) as exc:
        dup_row = _error(exc)
    try:
        case_obj = json.loads(case, object_pairs_hook=reject_duplicate_hook)
        case_row = classify_case_variant(case_obj)
    except (ValueError, json.JSONDecodeError) as exc:
        case_row = _error(exc)
    return dup_row, case_row


def python_casefold(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    dup_obj = json.loads(dup, object_pairs_hook=casefold_last_hook)
    case_obj = json.loads(case, object_pairs_hook=casefold_last_hook)
    return classify_duplicate(dup_obj), classify_case_variant(case_obj)


def _run_text(argv: list[str], text: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        argv,
        input=text,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def node_parse(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    node = shutil.which("node")
    if not node:
        missing = {
            "behaviour": "error",
            "error_type": "FileNotFoundError",
            "message": "node not on PATH",
            "assumed": False,
        }
        return missing, dict(missing)
    script = (
        "const fs=require('fs');"
        "const s=fs.readFileSync(0,'utf8');"
        "process.stdout.write(JSON.stringify(JSON.parse(s)));"
    )

    def one(raw: str, classifier: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        code, out, err = _run_text([node, "-e", script], raw)
        if code != 0:
            return {
                "behaviour": "error",
                "error_type": "NodeJSONParse",
                "message": (err or out)[:240],
                "assumed": False,
            }
        try:
            obj = json.loads(out)
        except json.JSONDecodeError as exc:
            return _error(exc)
        return classifier(obj)

    return one(dup, classify_duplicate), one(case, classify_case_variant)


def jq_parse(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    jq = shutil.which("jq")
    if not jq:
        missing = {
            "behaviour": "error",
            "error_type": "FileNotFoundError",
            "message": "jq not on PATH",
            "assumed": False,
        }
        return missing, dict(missing)

    def one(raw: str, classifier: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        code, out, err = _run_text([jq, "-c", "."], raw)
        if code != 0:
            return {
                "behaviour": "error",
                "error_type": "JqError",
                "message": (err or out)[:240],
                "assumed": False,
            }
        try:
            obj = json.loads(out)
        except json.JSONDecodeError as exc:
            return _error(exc)
        return classifier(obj)

    return one(dup, classify_duplicate), one(case, classify_case_variant)


def jsonschema_after_loads(dup: str, case: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        import jsonschema
    except ImportError as exc:
        row = _error(exc)
        return row, dict(row)

    def one(raw: str, classifier: Callable[[Any], dict[str, Any]]) -> dict[str, Any]:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _error(exc)
        row = classifier(obj)
        validator = jsonschema.Draft7Validator(INSTANCE_SCHEMA)
        errors = [e.message for e in validator.iter_errors(obj)]
        row = dict(row)
        row["validator"] = "jsonschema.Draft7Validator"
        row["schema_valid"] = len(errors) == 0
        row["schema_errors"] = errors[:4]
        row["parse_precedes_validator"] = "json.loads"
        return row

    return one(dup, classify_duplicate), one(case, classify_case_variant)


CONSUMERS: list[dict[str, Any]] = [
    {
        "id": "python-json.loads",
        "role": "live-consumer",
        "implementation": "CPython json.loads",
        "fn": python_loads,
        "uses_files": False,
    },
    {
        "id": "python-json.load",
        "role": "live-consumer",
        "implementation": "CPython json.load on UTF-8 files",
        "fn": python_load_file,
        "uses_files": True,
    },
    {
        "id": "python-json.JSONDecoder",
        "role": "live-consumer",
        "implementation": "CPython json.JSONDecoder.decode",
        "fn": python_decoder,
        "uses_files": False,
    },
    {
        "id": "node-JSON.parse",
        "role": "live-consumer",
        "implementation": "node JSON.parse then JSON.stringify",
        "fn": node_parse,
        "uses_files": False,
    },
    {
        "id": "jq",
        "role": "live-consumer",
        "implementation": "jq -c .",
        "fn": jq_parse,
        "uses_files": False,
    },
    {
        "id": "jsonschema-Draft7Validator",
        "role": "live-consumer",
        "implementation": "json.loads then jsonschema.Draft7Validator",
        "fn": jsonschema_after_loads,
        "uses_files": False,
    },
    {
        "id": "python-json-strict-duplicate-hook",
        "role": "strict-duplicate-control",
        "implementation": "json.loads object_pairs_hook that errors on repeated keys",
        "fn": python_strict_dup,
        "uses_files": False,
    },
    {
        "id": "python-json-casefold-hook",
        "role": "seeded-failure-class-control",
        "implementation": "json.loads object_pairs_hook that casefolds keys (last-wins)",
        "fn": python_casefold,
        "uses_files": False,
    },
]


def measure_all() -> list[dict[str, Any]]:
    dup_text = DUP_PATH.read_text(encoding="utf-8")
    case_text = CASE_PATH.read_text(encoding="utf-8")
    rows = []
    for spec in CONSUMERS:
        fn = spec["fn"]
        try:
            if spec["uses_files"]:
                dup_row, case_row = fn(DUP_PATH, CASE_PATH)
            else:
                dup_row, case_row = fn(dup_text, case_text)
        except Exception as exc:  # noqa: BLE001 - classify unexpected consumer crashes
            dup_row, case_row = _error(exc), _error(exc)
        rows.append(
            {
                "id": spec["id"],
                "role": spec["role"],
                "implementation": spec["implementation"],
                "available": dup_row.get("behaviour") != "error"
                or spec["role"] in {"strict-duplicate-control", "seeded-failure-class-control"}
                or spec["id"] in {"python-json-strict-duplicate-hook"},
                "duplicate_key": dup_row,
                "case_variant": case_row,
                "assumed": False,
            }
        )
    # Availability: a live consumer that errored because the binary is missing
    # is not "available". One that parsed is available. Strict hook errors on
    # purpose for duplicates.
    for row in rows:
        if row["role"] == "strict-duplicate-control":
            row["available"] = True
        elif row["role"] == "seeded-failure-class-control":
            row["available"] = True
        else:
            dup_b = row["duplicate_key"].get("behaviour")
            case_b = row["case_variant"].get("behaviour")
            row["available"] = dup_b != "error" or case_b != "error"
            if row["duplicate_key"].get("error_type") == "FileNotFoundError":
                row["available"] = False
    return rows


def live_case_insensitive(rows: list[dict[str, Any]]) -> bool:
    collapsing = {"casefold-collapse", "dropped-one"}
    for row in rows:
        if row.get("role") != "live-consumer":
            continue
        if not row.get("available"):
            continue
        if row.get("case_variant", {}).get("behaviour") in collapsing:
            return True
    return False
