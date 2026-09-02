#!/usr/bin/env python3
"""Third agent: survival judge.

Sees (artifact bytes, candidate). Does not import refute.py or find.py.
Does not read author labels. Closed defect vocabulary only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from util import REPO

CLOSED = frozenset(
    {
        "claimed_exists_missing",
        "claimed_gt_present",
        "probe_pass_scripts_absent",
        "schema_required_missing",
    }
)
PATH_KEYS = ("primary", "rel", "path", "output_path")
PATH_LIST_KEYS = ("ok_relpaths",)


def _repo_file(raw: str) -> Path | None:
    text = raw.replace("\\", "/").strip()
    if not text:
        return None
    if len(text) >= 3 and text[1:3] == ":/":
        return None
    if text.lower().startswith("c:/"):
        return None
    if text.startswith("file:"):
        text = text[5:]
    rel = text.lstrip("/")
    if rel.startswith("command-center/") or rel.startswith("tools/"):
        return REPO / rel
    return None


def _walk_exists(obj: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(obj, dict):
        local: list[str] = []
        for key in PATH_KEYS:
            val = obj.get(key)
            if isinstance(val, str) and val.strip():
                local.append(val)
        for key in PATH_LIST_KEYS:
            val = obj.get(key)
            if isinstance(val, list):
                local.extend(x for x in val if isinstance(x, str) and x.strip())
        if obj.get("exists") is True:
            paths.extend(local)
        for val in obj.values():
            paths.extend(_walk_exists(val))
    elif isinstance(obj, list):
        for val in obj:
            paths.extend(_walk_exists(val))
    return paths


def _scripts_absent(doc: dict) -> bool:
    nps = doc.get("named_probe_scripts_present")
    if isinstance(nps, dict) and nps and not any(bool(v) for v in nps.values()):
        return True
    blobs = [doc]
    nested = doc.get("validate")
    if isinstance(nested, dict):
        blobs.append(nested)
    for blob in blobs:
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


def _probe_pass_ids(doc: dict) -> set[str]:
    ids: set[str] = set()
    tests = doc.get("tests")
    if not isinstance(tests, list):
        validate = doc.get("validate")
        tests = validate.get("tests") if isinstance(validate, dict) else None
    if not isinstance(tests, list):
        return ids
    for item in tests:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or item.get("name") or "")
        result = str(item.get("result") or "").upper()
        if result == "PASS" and "named-probe" in tid.lower().replace("_", "-"):
            ids.add(tid)
    return ids


def survive(artifact_bytes: bytes, candidate: dict) -> dict:
    """Return {survive: bool, reason}. Ignores candidate['author']."""
    kind = str(candidate.get("kind") or "")
    if kind not in CLOSED:
        return {"survive": False, "reason": f"kind {kind!r} not a closed defect"}
    try:
        text = artifact_bytes.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"survive": False, "reason": f"artifact unreadable {type(exc).__name__}"}
    if not isinstance(doc, dict):
        return {"survive": False, "reason": "artifact is not a JSON object"}

    if kind == "claimed_exists_missing":
        claimed = str(candidate.get("claimed_path") or "")
        live = _walk_exists(doc)
        if claimed not in live:
            return {"survive": False, "reason": "claimed_path not an exists:true path in bytes"}
        target = _repo_file(claimed)
        if target is not None and target.is_file():
            return {"survive": False, "reason": "path is present on this worktree"}
        return {"survive": True, "reason": "exists:true path absent on this worktree"}

    if kind == "claimed_gt_present":
        claimed = doc.get("artifacts_claimed")
        present = doc.get("artifacts_present")
        if not (isinstance(claimed, int) and isinstance(present, int)):
            return {"survive": False, "reason": "count fields missing"}
        if claimed > present:
            if candidate.get("claimed") not in (None, claimed):
                return {"survive": False, "reason": "candidate claimed count mismatch"}
            return {"survive": True, "reason": "artifacts_claimed exceeds artifacts_present"}
        return {"survive": False, "reason": "counts do not contradict"}

    if kind == "probe_pass_scripts_absent":
        if not _scripts_absent(doc):
            return {"survive": False, "reason": "scripts are not absent"}
        tid = str(candidate.get("test_id") or "")
        if tid not in _probe_pass_ids(doc):
            return {"survive": False, "reason": "named-probe PASS id not in bytes"}
        return {"survive": True, "reason": "PASS recorded while scripts absent"}

    if kind == "schema_required_missing":
        required = doc.get("required")
        props = doc.get("properties")
        key = candidate.get("missing_key")
        if not (isinstance(required, list) and isinstance(props, dict)):
            return {"survive": False, "reason": "not a JSON Schema object"}
        if isinstance(key, str) and key in required and key not in props:
            return {"survive": True, "reason": "required key missing from properties"}
        return {"survive": False, "reason": "schema required-set is covered"}

    return {"survive": False, "reason": "unhandled kind"}
