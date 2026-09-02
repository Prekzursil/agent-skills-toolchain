"""Load TEST-REGISTRY.json into a set of test ids.

Suite `tests` integers are counts, not ids: they cannot join to collected
node ids, so they are recorded as count-only rows rather than invented ids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIVE_REGISTRY = REPO / "command-center" / "TEST-REGISTRY.json"


def _as_id(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, dict):
        for key in ("id", "nodeid", "node_id", "collected_id"):
            raw = value.get(key)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


def load_registry(path: Path | None = None) -> dict[str, Any]:
    path = path or LIVE_REGISTRY
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            "present": False,
            "path": str(path),
            "ids": [],
            "function_names": [],
            "count_only_suites": [],
            "granularity": "absent",
            "raw_entry_count": 0,
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"{path} is not a JSON object")
    ids: list[str] = []
    names: list[str] = []
    count_only: list[dict[str, Any]] = []

    for item in doc.get("entries") or []:
        nid = _as_id(item)
        if nid:
            ids.append(nid)
    for item in doc.get("tests") or []:
        nid = _as_id(item)
        if nid:
            ids.append(nid)
    for item in doc.get("nodeids") or []:
        nid = _as_id(item)
        if nid:
            ids.append(nid)

    for suite in doc.get("suites") or []:
        if not isinstance(suite, dict):
            continue
        suite_path = str(suite.get("path") or "").replace("\\", "/")
        tests = suite.get("tests")
        if isinstance(tests, int):
            count_only.append({"path": suite_path, "tests": tests})
            continue
        if isinstance(tests, list):
            for item in tests:
                nid = _as_id(item)
                if not nid:
                    continue
                if "::" in nid or "/" in nid:
                    ids.append(nid)
                else:
                    names.append(nid)
                    if suite_path:
                        ids.append(f"{suite_path}::{nid}")

    for inv in doc.get("invariants") or []:
        if not isinstance(inv, dict):
            continue
        for item in inv.get("tests") or []:
            nid = _as_id(item)
            if not nid:
                continue
            if "::" in nid:
                ids.append(nid)
            else:
                names.append(nid)

    ids = sorted(set(ids))
    names = sorted(set(names))
    if ids:
        granularity = "nodeid"
    elif names:
        granularity = "function-name"
    elif count_only:
        granularity = "suite-count"
    else:
        granularity = "empty"
    return {
        "present": True,
        "path": str(path),
        "ids": ids,
        "function_names": names,
        "count_only_suites": count_only,
        "granularity": granularity,
        "raw_entry_count": len(ids),
    }
