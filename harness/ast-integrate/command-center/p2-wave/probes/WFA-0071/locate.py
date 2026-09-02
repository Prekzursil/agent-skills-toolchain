#!/usr/bin/env python3
"""Locate the workflow candidate registry and salvage inputs on this estate.

Read-only. Does not copy Windows paths into the repo; reports hit/miss per path.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]

REGISTRY_CANDIDATES = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    str(Path.home() / ".claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json"),
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/sources/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/p2-wave/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "command-center/_wfa2_entries.json",
    "command-center/wfa/08-WORKFLOW-CANDIDATE-REGISTRY.json",
)

SALVAGE_CANDIDATES = (
    "command-center/wfa/WFA-0022-sweep-abandoned-salvage.json",
    "command-center/p2-wave/probes/WFA-0022/WFA-0022-sweep-abandoned-salvage.json",
)

EXPECTED_RETIRE_N = 24
EXPECTED_SOURCE_SHA256 = (
    "4791c7a628e5bf1f5492c56a7b06bdb636f5a66829c0145ecb27d3f0b0f0885a"
)


def _as_path(spec: str) -> Path:
    p = Path(spec)
    if p.is_absolute() or (len(spec) >= 3 and spec[1] == ":"):
        return p
    return REPO / spec


def probe_path(spec: str) -> dict:
    path = _as_path(spec)
    exists = path.is_file()
    rec: dict = {
        "path": spec,
        "resolved": str(path),
        "exists": exists,
        "bytes": 0,
        "sha256": None,
    }
    if not exists:
        return rec
    raw = path.read_bytes()
    rec["bytes"] = len(raw)
    rec["sha256"] = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
    return rec


def git_available() -> dict:
    git_dir = REPO / ".git"
    return {
        "repo_is_git": git_dir.exists(),
        "git_dir": str(git_dir),
        "named_commit_retrieval": "unavailable" if not git_dir.exists() else "available",
    }


def candidate_rows(doc) -> list[dict]:
    cands: list | None = None
    if isinstance(doc, list):
        cands = doc
    elif isinstance(doc, dict):
        for key in ("candidates", "records", "items", "workflows", "entries"):
            val = doc.get(key)
            if isinstance(val, list):
                cands = val
                break
        if cands is None and isinstance(doc.get("work_units"), list):
            cands = doc["work_units"]
    return [row for row in (cands or []) if isinstance(row, dict)]


def row_classification(row: dict) -> str:
    return str(
        row.get("classification")
        or row.get("disposition")
        or row.get("verdict")
        or ""
    ).upper()


def extract_retire(doc) -> list[dict]:
    return [row for row in candidate_rows(doc) if row_classification(row) == "RETIRE"]


def classified_n(doc) -> int:
    return sum(1 for row in candidate_rows(doc) if row_classification(row))


def is_authoritative_registry(rec: dict, doc) -> tuple[bool, str]:
    """A file on disk is not the 284-row classified registry by existing.

    `_wfa2_entries.json` is a markdown inventory (id/name only). Control
    fixtures in other units are reconstructions. Only a SHA match or a
    classified RETIRE n=24 census counts as the live registry.
    """
    if rec.get("sha256") == EXPECTED_SOURCE_SHA256:
        return True, "sha256-match"
    if doc is None:
        return False, "unparseable"
    n_class = classified_n(doc)
    if n_class < 20:
        return False, "no-classification-fields"
    n_retire = len(extract_retire(doc))
    if n_retire == EXPECTED_RETIRE_N:
        return True, "classified-retire-n-24"
    return False, f"classified-but-retire-n={n_retire}"


def load_json_file(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def locate_registry() -> dict:
    hits: list[dict] = []
    misses: list[dict] = []
    rejected: list[dict] = []
    retire: list[dict] = []
    chosen = None
    for spec in REGISTRY_CANDIDATES:
        rec = probe_path(spec)
        if not rec["exists"]:
            misses.append(rec)
            continue
        doc = load_json_file(Path(rec["resolved"]))
        rec["json_ok"] = doc is not None
        rec["matches_expected_sha"] = rec["sha256"] == EXPECTED_SOURCE_SHA256
        rec["classified_n"] = classified_n(doc) if doc is not None else 0
        rec["retire_n"] = len(extract_retire(doc)) if doc is not None else 0
        ok, reason = is_authoritative_registry(rec, doc)
        rec["registry_reason"] = reason
        if not ok:
            rec["reject_reason"] = reason
            rejected.append(rec)
            continue
        hits.append(rec)
        if chosen is None:
            chosen = rec
            retire = extract_retire(doc) if doc is not None else []
    salvage_hits = [probe_path(s) for s in SALVAGE_CANDIDATES]
    return {
        "chosen": chosen,
        "hits": hits,
        "misses": misses,
        "rejected": rejected,
        "retire_records": retire,
        "retire_n": len(retire),
        "expected_retire_n": EXPECTED_RETIRE_N,
        "salvage": salvage_hits,
        "git": git_available(),
        "worktree": str(REPO),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
    }
