#!/usr/bin/env python3
"""Load CNF-0138 inputs: frame, false-pass, live vs fixture."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
THRESHOLD_REL = "command-center/confirmation/CNF-0138-frozen-threshold.json"
FRAME_LIVE = REPO / "command-center/receipts/CNF-0137.json"
PHI_LIVE = REPO / "command-center/receipts/CNF-0133.json"
FRAME_FIX = HERE / "fixtures/sampling_frame.json"
PHI_CHECKED = HERE / "fixtures/false_pass_checked.json"
PHI_NOT_CHECKED = HERE / "fixtures/false_pass_not_checked.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def git_head() -> dict:
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "git_available": False,
            "head": None,
            "path_last_commit_time": None,
            "error": "git-not-runnable",
        }
    if inside.returncode != 0:
        err = (inside.stderr or inside.stdout or "").strip()
        return {
            "git_available": False,
            "head": None,
            "path_last_commit_time": None,
            "error": err[:240] or "not-a-git-repository",
        }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=10,
    )
    path_ts = subprocess.run(
        ["git", "log", "-1", "--format=%cI", "--", THRESHOLD_REL],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "git_available": True,
        "head": (head.stdout or "").strip() or None,
        "path_last_commit_time": (path_ts.stdout or "").strip() or None,
        "error": None,
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_frame() -> tuple[dict, str]:
    if FRAME_LIVE.is_file() and FRAME_LIVE.stat().st_size > 0:
        doc = load_json(FRAME_LIVE)
        return doc, "live-CNF-0137"
    return load_json(FRAME_FIX), "fixture"


def extract_strata(frame: dict) -> list[dict]:
    if isinstance(frame.get("strata"), list) and frame["strata"]:
        return [s for s in frame["strata"] if isinstance(s, dict)]
    for key in ("stratum_table", "sampling_frame", "frame"):
        block = frame.get(key)
        if isinstance(block, dict) and isinstance(block.get("strata"), list):
            return [s for s in block["strata"] if isinstance(s, dict)]
        if isinstance(block, list) and block:
            return [s for s in block if isinstance(s, dict)]
    raise ValueError("sampling frame has no strata list")


def load_false_pass_checked() -> tuple[dict, str]:
    if PHI_LIVE.is_file() and PHI_LIVE.stat().st_size > 0:
        doc = load_json(PHI_LIVE)
        # Prefer a numeric measured rate if CNF-0133 published one.
        for key in ("false_pass_rate", "false_pass", "phi"):
            val = doc.get(key)
            if isinstance(val, dict) and val.get("status") == "CHECKED":
                return val, "live-CNF-0133"
            if isinstance(val, (int, float)):
                return {
                    "status": "CHECKED",
                    "rate": float(val),
                    "provenance": "CNF-0133 receipt numeric field",
                    "cnf_0133_present": True,
                }, "live-CNF-0133"
        if doc.get("status") == "CHECKED" and isinstance(doc.get("rate"), (int, float)):
            return doc, "live-CNF-0133"
    return load_json(PHI_CHECKED), "fixture-conservative-bound"


def freeze_or_load_threshold(tau: float, design: dict) -> dict:
    path = REPO / THRESHOLD_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    git = git_head()
    if path.is_file() and path.stat().st_size > 0:
        existing = load_json(path)
        # Resume: never retune a frozen threshold.
        if abs(float(existing.get("rate")) - tau) > 1e-12:
            raise ValueError(
                f"frozen threshold rate {existing.get('rate')} != design tau {tau}; "
                "do not retune"
            )
        existing["git"] = git
        existing["git_available"] = bool(git.get("git_available"))
        return existing
    frozen_at = utc_now()
    doc = {
        "unit_id": "CNF-0138",
        "kind": "pre-registered-expansion-threshold",
        "spec_anchor": "_USER-PROMPTS.md:11041",
        "rate": tau,
        "comparison": "strict_gt",
        "exactly_at_threshold": "silent",
        "expand_when": "observed_error_rate > tau",
        "frozen_at": frozen_at,
        "git": git,
        "git_available": bool(git.get("git_available")),
        "timestamp_source": (
            "git-path-committer-date"
            if git.get("path_last_commit_time")
            else "declared_frozen_at"
        ),
        "design": design,
        "note": (
            "Threshold recorded before confirmation runs on this worktree. "
            "Do not fit tau to an observed stratum rate."
        ),
    }
    path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return doc
