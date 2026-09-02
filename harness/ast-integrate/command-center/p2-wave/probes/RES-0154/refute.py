#!/usr/bin/env python3
"""Honest and noisy refuters. Honest does not see gold labels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from util import REPO

KIND_EXISTS = "claimed_exists_missing"
KIND_COUNT = "claimed_gt_present"
KIND_PROBE = "probe_pass_scripts_absent"
KIND_SCHEMA = "schema_required_missing"
KIND_NIT = "style-nit"

PATH_KEYS = ("primary", "rel", "path", "output_path")
PATH_LIST_KEYS = ("ok_relpaths",)


def _load(rel: str) -> Any:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def _repo_file(raw: str) -> Path | None:
    text = raw.replace("\\", "/").strip()
    if not text:
        return None
    if len(text) >= 3 and text[1:3] == ":/":
        return None
    if text.startswith("C:/") or text.startswith("c:/"):
        return None
    if text.startswith("file:"):
        text = text[5:]
    rel = text.lstrip("/")
    if rel.startswith("command-center/") or rel.startswith("tools/"):
        return REPO / rel
    return None


def _walk_exists_claims(obj: Any, trail: str = "") -> list[tuple[str, list[str]]]:
    found: list[tuple[str, list[str]]] = []
    if isinstance(obj, dict):
        paths: list[str] = []
        for key in PATH_KEYS:
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                paths.append(val)
        for key in PATH_LIST_KEYS:
            val = obj.get(key)
            if isinstance(val, list):
                paths.extend(x for x in val if isinstance(x, str) and x.strip())
        if obj.get("exists") is True and paths:
            found.append((trail or "$", paths))
        for key, val in obj.items():
            child = f"{trail}.{key}" if trail else key
            found.extend(_walk_exists_claims(val, child))
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            found.extend(_walk_exists_claims(val, f"{trail}[{i}]"))
    return found


def _scripts_absent(doc: Any) -> bool:
    if not isinstance(doc, dict):
        return False
    nps = doc.get("named_probe_scripts_present")
    if isinstance(nps, dict) and nps and not any(bool(v) for v in nps.values()):
        return True
    for blob in (doc, doc.get("validate") or {}):
        if not isinstance(blob, dict):
            continue
        if blob.get("probe1_on_disk") is False and blob.get("probe2_on_disk") is False:
            return True
        named = blob.get("named_probes")
        if isinstance(named, dict):
            flags = []
            for key in ("probe1", "probe2"):
                node = named.get(key)
                if isinstance(node, dict) and "exists" in node:
                    flags.append(bool(node.get("exists")))
            if flags and not any(flags):
                return True
    return False


def _named_probe_pass(doc: Any) -> list[str]:
    ids: list[str] = []
    tests = doc.get("tests") if isinstance(doc, dict) else None
    if not isinstance(tests, list):
        validate = doc.get("validate") if isinstance(doc, dict) else None
        if isinstance(validate, dict):
            tests = validate.get("tests")
    if not isinstance(tests, list):
        return ids
    for item in tests:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or item.get("name") or "")
        result = str(item.get("result") or "").upper()
        if result == "PASS" and "named-probe" in tid.lower().replace("_", "-"):
            ids.append(tid)
    return ids


def honest_findings(rel: str) -> list[dict]:
    """Mechanical defects only. Gold labels are not an input."""
    doc = _load(rel)
    out: list[dict] = []
    if not isinstance(doc, dict):
        return out

    for trail, paths in _walk_exists_claims(doc):
        for raw in paths:
            target = _repo_file(raw)
            missing = target is None or not target.is_file()
            if missing:
                out.append(
                    {
                        "kind": KIND_EXISTS,
                        "rel": rel,
                        "trail": trail,
                        "claimed_path": raw,
                        "detail": "exists:true but path is not a file on this worktree",
                    }
                )

    claimed = doc.get("artifacts_claimed")
    present = doc.get("artifacts_present")
    if isinstance(claimed, int) and isinstance(present, int) and claimed > present:
        out.append(
            {
                "kind": KIND_COUNT,
                "rel": rel,
                "claimed": claimed,
                "present": present,
                "detail": f"artifacts_claimed={claimed} > artifacts_present={present}",
            }
        )

    if _scripts_absent(doc):
        for tid in _named_probe_pass(doc):
            out.append(
                {
                    "kind": KIND_PROBE,
                    "rel": rel,
                    "test_id": tid,
                    "detail": f"test {tid} result PASS while named probe scripts are absent",
                }
            )

    required = doc.get("required")
    props = doc.get("properties")
    if isinstance(required, list) and isinstance(props, dict):
        for key in required:
            if isinstance(key, str) and key not in props:
                out.append(
                    {
                        "kind": KIND_SCHEMA,
                        "rel": rel,
                        "missing_key": key,
                        "detail": f"required key {key!r} not in properties",
                    }
                )
    return out


def noisy_findings(rel: str) -> list[dict]:
    """Honest findings plus a volume floor nit on every artifact."""
    items = honest_findings(rel)
    items.append(
        {
            "kind": KIND_NIT,
            "rel": rel,
            "detail": "artifact could be shorter",
        }
    )
    return items
