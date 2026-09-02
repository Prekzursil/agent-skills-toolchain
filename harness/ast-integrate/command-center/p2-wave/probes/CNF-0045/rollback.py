#!/usr/bin/env python3
"""Dry-run rollback of a deploy target toward the repo tree.

CNF-0045 hard rule: never write into a live tree. apply=True is a hard failure.
Planned mutations are recorded, not executed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from classify import (
    LIVE_AHEAD,
    LIVE_ONLY,
    NEEDS_RECONCILE,
    NO_OP,
    REFUSE,
    classify_trees,
    walk_rel,
)

APPLY_FORBIDDEN = (
    "FAILED:CNF-0045 premature-write: apply/live write is a hard failure for this unit"
)


def fingerprint_tree(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {"__absent__": "1"}
    out: dict[str, str] = {}
    for rel, path in sorted(walk_rel(root).items()):
        data = path.read_bytes()
        st = path.stat()
        digest = hashlib.sha256(data).hexdigest()
        out[rel] = f"{digest}:{len(data)}:{st.st_mtime_ns}"
    return out


def fingerprint_path(path: Path) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
    }
    if path.is_file():
        data = path.read_bytes()
        st = path.stat()
        rec.update(
            {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "mtime_ns": st.st_mtime_ns,
                "file_count": 1,
            }
        )
    elif path.is_dir():
        rec["tree"] = fingerprint_tree(path)
        rec["file_count"] = len(rec["tree"])
    else:
        rec["file_count"] = 0
    return rec


def live_only_overwrite_transcript(row: dict[str, Any]) -> dict[str, Any] | None:
    if not row.get("live_unique_line_count"):
        return None
    return {
        "path": row["path"],
        "classification": row["classification"],
        "rollback_action": row["rollback_action"],
        "naive_action": row["naive_action"],
        "live_unique_line_count": row["live_unique_line_count"],
        "live_unique_bytes": row["live_unique_bytes"],
        "live_unique_sha256": row["live_unique_sha256"],
        "live_unique_lines_sample": row["live_unique_lines_sample"],
        "would_overwrite_if_naive": row["naive_would_destroy_live_unique"],
    }


def plan_rollback(
    repo_root: Path,
    live_root: Path,
    *,
    dry_run: bool = True,
    apply: bool = False,
) -> dict[str, Any]:
    if apply or not dry_run:
        return {
            "ok": False,
            "hard_failure": True,
            "classification": "premature-write",
            "error": APPLY_FORBIDDEN,
            "writes_executed": None,
            "dry_run": False,
        }
    live_before = fingerprint_tree(live_root)
    repo_before = fingerprint_tree(repo_root)
    table = classify_trees(repo_root, live_root)
    refused = [r for r in table["rows"] if r["rollback_action"] == REFUSE]
    would_mutate = [
        r for r in table["rows"] if r["rollback_action"] not in {NO_OP, REFUSE}
    ]
    destroy_if_naive = [r for r in table["rows"] if r["naive_would_destroy_live_unique"]]
    two_directional = [
        r
        for r in table["rows"]
        if r["classification"] in {NEEDS_RECONCILE, LIVE_AHEAD, LIVE_ONLY}
    ]
    transcript = []
    for row in table["rows"]:
        entry = {
            "path": row["path"],
            "classification": row["classification"],
            "direction": row["direction"],
            "action": row["rollback_action"],
            "executed": False,
            "reason": _reason(row),
        }
        lost = live_only_overwrite_transcript(row)
        if lost:
            entry["live_only_bytes_naive_would_overwrite"] = lost
        transcript.append(entry)

    live_after = fingerprint_tree(live_root)
    repo_after = fingerprint_tree(repo_root)
    live_unchanged = live_before == live_after
    repo_unchanged = repo_before == repo_after
    return {
        "ok": live_unchanged and repo_unchanged,
        "hard_failure": False,
        "dry_run": True,
        "apply": False,
        "writes_executed": 0,
        "live_tree_unchanged": live_unchanged,
        "repo_tree_unchanged": repo_unchanged,
        "two_directional_detected_before_write": True,
        "refused_count": len(refused),
        "planned_mutations_not_executed": len(would_mutate),
        "naive_would_destroy_count": len(destroy_if_naive),
        "two_directional_count": len(two_directional),
        "live_fingerprint_before": _digest_map(live_before),
        "live_fingerprint_after": _digest_map(live_after),
        "classification_table": table,
        "dry_run_transcript": transcript,
        "naive_destruction_transcript": [
            live_only_overwrite_transcript(r) for r in destroy_if_naive
        ],
        "refused_paths": [r["path"] for r in refused],
        "needs_reconcile_paths": [
            r["path"] for r in table["rows"] if r["classification"] == NEEDS_RECONCILE
        ],
        "identical_noop_paths": [
            r["path"]
            for r in table["rows"]
            if r["classification"] == "IDENTICAL" and r["rollback_action"] == NO_OP
        ],
    }


def _digest_map(fp: dict[str, str]) -> str:
    blob = json.dumps(fp, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _reason(row: dict[str, Any]) -> str:
    cls = row["classification"]
    action = row["rollback_action"]
    if action == NO_OP:
        return "byte-identical; classifier no-op (not flagging everything)"
    if action == REFUSE:
        return (
            f"{cls}: live side holds unique content; rollback of deploy target "
            "would destroy live-only bytes; flagged, not auto-resolved"
        )
    if action == "WOULD-REPLACE-LIVE":
        return (
            f"{cls}: live is a line-subset of repo; dry-run records a replace "
            "and does not execute it"
        )
    if action == "WOULD-REWRITE-EOL":
        return "EOL-only after LF normalisation; dry-run does not rewrite"
    if action == "WOULD-CREATE-ON-LIVE":
        return "repo-only path; dry-run does not create on live"
    return f"{cls}/{action}"
