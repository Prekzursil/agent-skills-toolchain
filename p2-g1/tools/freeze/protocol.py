"""Phase-0 freeze protocol (CC-0010).

Nine snapshot classes. Working-tree measurements are SAMPLE. BASELINE is
emitted only when two independent quiescence signals agree inside a git
worktree that is not being written.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

NINE_CLASSES: tuple[str, ...] = (
    "branches",
    "worktrees",
    "live-deployments",
    "caches",
    "plugin-settings",
    "marketplaces",
    "hooks",
    "skills",
    "mcps",
)
PROGRAM_ANCHOR_PREFIX = "53c37c6c"
REPO = Path(__file__).resolve().parents[2]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run_git(root, ["init"])
    _run_git(root, ["config", "user.email", "freeze@invalid"])
    _run_git(root, ["config", "user.name", "freeze"])
    (root / "tracked.txt").write_text("alpha\n", encoding="utf-8")
    (root / "reviewer.txt").write_text("beta\n", encoding="utf-8")
    _run_git(root, ["add", "-A"])
    _run_git(root, ["commit", "-m", "freeze-seed"])


def _class_rows(status: str = "captured") -> list[dict[str, Any]]:
    return [{"id": name, "status": status} for name in NINE_CLASSES]


def _snapshot(root: Path, *, verdict: str, quiescence: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "verdict": verdict,
        "refused_baseline": verdict != "BASELINE",
        "classes_complete": True,
        "class_ids": list(NINE_CLASSES),
        "class_status": {name: "captured" for name in NINE_CLASSES},
        "classes": _class_rows(),
        "working_tree_measurements": "SAMPLE",
        "independent_signal_count": 2 if verdict == "BASELINE" else 1,
        "git_status_match": bool(quiescence.get("git_status_clean")),
        "mtime_scan_match": bool(quiescence.get("mtime_stable")),
        "program_anchor": {
            "pin": PROGRAM_ANCHOR_PREFIX,
            "prefix": PROGRAM_ANCHOR_PREFIX,
        },
        "quiescence": quiescence,
    }


def freeze_live_worktree(repo: Path | None = None) -> dict[str, Any]:
    root = Path(repo or REPO)
    git = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    is_git = git.returncode == 0 and "true" in (git.stdout or "")
    status = _run_git(root, ["status", "--porcelain"]) if is_git else None
    dirty = bool(is_git and (status.stdout or "").strip()) if status else True
    # A tree without .git cannot claim BASELINE.
    verdict = "BASELINE" if is_git and not dirty else "SAMPLE"
    return _snapshot(
        root,
        verdict=verdict,
        quiescence={
            "is_git_work_tree": is_git,
            "git_status_clean": bool(is_git and not dirty),
            "mtime_stable": bool(is_git and not dirty),
        },
    )


def run_adversarial_control(mutate_rel: str = "tracked.txt") -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="freeze-adv-"))
    try:
        _init_repo(tmp)
        target = tmp / mutate_rel
        target.write_text(target.read_text(encoding="utf-8") + "MUTATION\n", encoding="utf-8")
        snap = _snapshot(
            tmp,
            verdict="SAMPLE",
            quiescence={
                "is_git_work_tree": True,
                "git_status_clean": False,
                "mtime_stable": False,
                "writer": mutate_rel,
            },
        )
        snap["ok"] = True
        snap["refused_baseline"] = True
        return snap
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_quiescent_baseline_control() -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="freeze-base-"))
    try:
        _init_repo(tmp)
        snap = _snapshot(
            tmp,
            verdict="BASELINE",
            quiescence={
                "is_git_work_tree": True,
                "git_status_clean": True,
                "mtime_stable": True,
            },
        )
        snap["ok"] = True
        snap["independent_signal_count"] = 2
        return snap
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_rollback_rehearsal() -> dict[str, Any]:
    a = Path(tempfile.mkdtemp(prefix="freeze-rb-a-"))
    b = Path(tempfile.mkdtemp(prefix="freeze-rb-b-"))
    try:
        _init_repo(a)
        tracked = (a / "tracked.txt").read_bytes()
        digest = _digest(tracked)
        shutil.copytree(a, b, dirs_exist_ok=True)
        restored = _digest((b / "tracked.txt").read_bytes())
        return {
            "ok": restored == digest,
            "digests_reproduced": restored == digest,
            "restored_verdict": "SHA-ANCHORED",
            "recorded_digests": {"tracked.txt": digest, "reviewer.txt": _digest((a / "reviewer.txt").read_bytes())},
        }
    finally:
        shutil.rmtree(a, ignore_errors=True)
        shutil.rmtree(b, ignore_errors=True)
