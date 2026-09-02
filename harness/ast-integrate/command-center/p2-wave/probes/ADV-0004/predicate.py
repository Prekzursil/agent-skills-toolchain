"""Readers under test: schema, sentinel-substring, G-1-like, shared reducer."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
from jsonschema.validators import validator_for

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from common import REPO, REDUCER_DIR_REL  # noqa: E402


def schema_accepts(raw: bytes, schema: dict[str, Any]) -> dict[str, Any]:
    """Parse + jsonschema. This is the schema-reader completion predicate."""
    if not raw:
        return {"accept": False, "reason": "empty"}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {"accept": False, "reason": f"decode:{exc}"}
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"accept": False, "reason": f"json:{exc.msg}"}
    try:
        cls = validator_for(schema)
        cls(schema).validate(doc)
    except jsonschema.exceptions.ValidationError as exc:
        return {"accept": False, "reason": f"schema:{exc.message}"}
    except jsonschema.exceptions.SchemaError as exc:
        return {"accept": False, "reason": f"schema-unusable:{exc.message}"}
    except RecursionError:
        return {"accept": False, "reason": "schema-recursion"}
    return {"accept": True, "reason": "schema-valid"}


def sentinel_substring_accepts(raw: bytes, sentinel: str) -> dict[str, Any]:
    """Dangerous reader: token presence only. Does not parse."""
    if not sentinel:
        return {"accept": False, "reason": "no-sentinel-token"}
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception as exc:  # pragma: no cover
        return {"accept": False, "reason": str(exc)}
    if sentinel in text:
        return {"accept": True, "reason": "sentinel-substring"}
    return {"accept": False, "reason": "sentinel-absent"}


def g1_like_accepts(raw: bytes, sentinel: str) -> dict[str, Any]:
    """G-1 measure subset: parse JSON, not BLOCKED, sentinel in text."""
    if not raw:
        return {"accept": False, "reason": "empty"}
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"accept": False, "reason": f"unparseable:{type(exc).__name__}"}
    if isinstance(doc, dict):
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return {"accept": False, "reason": f"self-declared:{st}"}
    if sentinel and sentinel not in text:
        return {"accept": False, "reason": "sentinel-absent"}
    return {"accept": True, "reason": "g1-parse-and-sentinel"}


def load_reducer():
    path = REPO / REDUCER_DIR_REL / "reducer.py"
    sys.path.insert(0, str(path.parent))
    import reducer as R  # noqa: E402

    return path, R


def reducer_accepts(workspace: Path) -> dict[str, Any]:
    _path, R = load_reducer()
    judged = R.judge(workspace, process_exit_code=0)
    return {
        "accept": judged.get("verdict") == "ACCEPT",
        "reason": judged.get("overall"),
        "failing": judged.get("failing") or [],
        "verdict": judged.get("verdict"),
        "exit_code_consulted_for_complete": judged.get(
            "exit_code_consulted_for_complete"
        ),
    }
