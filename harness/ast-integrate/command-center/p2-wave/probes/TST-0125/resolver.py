#!/usr/bin/env python3
"""Per-project coverage-threshold SSOT resolver for TST-0125.

Thresholds live in that project's .coverage-thresholds.json and its declared
enforcement command. Absence is NOT-CHECKED, never a silent pass. A sibling
or hardcoded command is a dead command here.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

THRESHOLDS_NAME = ".coverage-thresholds.json"
NOT_CHECKED = "NOT-CHECKED"
PASS = "PASS"
FAIL = "FAIL"

SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
        "eggs",
        ".next",
        "coverage",
        "htmlcov",
        ".turbo",
        ".nx",
        "site-packages",
    }
)
PROJECT_MARKERS = (
    "pyproject.toml",
    "package.json",
    "pytest.ini",
    "Cargo.toml",
    "go.mod",
    THRESHOLDS_NAME,
)


def load_thresholds(project: Path) -> tuple[Path | None, dict | None, str]:
    path = Path(project) / THRESHOLDS_NAME
    if not path.is_file():
        return None, None, "no .coverage-thresholds.json in this project"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return path, None, f"unparseable:{type(exc).__name__}"
    if not isinstance(data, dict):
        return path, None, "thresholds-file-not-object"
    return path, data, ""


def declared_enforcement_command(data: dict) -> str | None:
    enf = data.get("enforcement")
    if isinstance(enf, dict):
        cmd = enf.get("command")
        if isinstance(cmd, str) and cmd.strip():
            return cmd.strip()
    for key in ("enforcement_command", "command"):
        cmd = data.get(key)
        if isinstance(cmd, str) and cmd.strip():
            return cmd.strip()
    return None


# Local interpreters the probes plant (`python3 enforce.py`) plus POSIX true/false.
# Product suites (pnpm/npm/pytest/cargo) stay NOT-RUN in a live-tree census so this
# unit cannot spawn a 45s coverage job as a side effect of answering the question.
_LOCAL_RUNNERS = frozenset(
    {"python", "python3", "python3.11", "python3.12", "python3.13", "true", "false"}
)


def is_local_enforcement_command(cmd: str) -> bool:
    parts = cmd.strip().split()
    if not parts:
        return False
    return Path(parts[0]).name.lower() in _LOCAL_RUNNERS


def _rel_to(path: Path, root: Path | None) -> str:
    if root is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def evaluate_project(
    project: Path,
    *,
    repo: Path | None = None,
    run: bool = True,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Evaluate one project root. Never returns PASS when the file is absent."""
    project = Path(project).resolve()
    rel_project = _rel_to(project, repo) if repo is not None else str(project)
    path, data, err = load_thresholds(project)
    base: dict[str, Any] = {
        "project": rel_project,
        "has_thresholds_file": path is not None,
        "thresholds_file": _rel_to(path, repo) if path is not None else None,
        "thresholds": None,
        "enforcement_command": None,
        "coverage_gated": path is not None,
        "exit_code": None,
        "stdout_tail": "",
        "stderr_tail": "",
    }
    if path is None:
        return {
            **base,
            "verdict": NOT_CHECKED,
            "reason": err,
        }
    if data is None:
        return {
            **base,
            "verdict": NOT_CHECKED,
            "reason": err,
        }
    cmd = declared_enforcement_command(data)
    thresholds = data.get("thresholds")
    base["thresholds"] = thresholds
    base["enforcement_command"] = cmd
    if not cmd:
        return {
            **base,
            "verdict": NOT_CHECKED,
            "reason": "thresholds file present but no enforcement.command declared",
        }
    if not run:
        return {
            **base,
            "verdict": "NOT-RUN",
            "reason": "enforcement command not executed (run=false)",
        }
    if not is_local_enforcement_command(cmd):
        return {
            **base,
            "verdict": "NOT-RUN",
            "reason": (
                "thresholds file present; enforcement.command is a product-suite "
                f"invocation ({cmd!r}) and is not executed by this census. "
                "Named probes plant and run a per-project python command instead."
            ),
        }
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(project),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            **base,
            "verdict": FAIL,
            "reason": "enforcement command timed out",
            "exit_code": 124,
        }
    except OSError as exc:
        return {
            **base,
            "verdict": FAIL,
            "reason": f"enforcement command could not start: {type(exc).__name__}",
            "exit_code": 127,
        }
    out = (proc.stdout or "")[-1500:]
    err_out = (proc.stderr or "")[-1500:]
    if proc.returncode == 0:
        verdict = PASS
        reason = (
            "enforcement command from "
            f"{_rel_to(path, repo)} exited 0"
        )
    else:
        verdict = FAIL
        reason = (
            "enforcement command from "
            f"{_rel_to(path, repo)} exited {proc.returncode}"
        )
    return {
        **base,
        "verdict": verdict,
        "reason": reason,
        "exit_code": proc.returncode,
        "stdout_tail": out,
        "stderr_tail": err_out,
    }


def prune_dirnames(dirpath: Path, dirnames: list[str], repo: Path) -> None:
    keep: list[str] = []
    for name in dirnames:
        if name in SKIP_DIR_NAMES or name.endswith(".egg-info"):
            continue
        child = dirpath / name
        try:
            parts = child.resolve().relative_to(repo.resolve()).parts
        except ValueError:
            continue
        if "probes" in parts and "runtime" in parts:
            continue
        keep.append(name)
    dirnames[:] = keep


def discover_projects(repo: Path) -> list[Path]:
    repo = Path(repo).resolve()
    found: dict[str, Path] = {}
    for dirpath_str, dirnames, filenames in os.walk(repo):
        dirpath = Path(dirpath_str)
        prune_dirnames(dirpath, dirnames, repo)
        names = set(filenames)
        if not any(marker in names for marker in PROJECT_MARKERS):
            continue
        rel = dirpath.relative_to(repo).as_posix() or "."
        found[rel] = dirpath
    return [found[k] for k in sorted(found)]


def census(repo: Path, *, run: bool = True, timeout: float = 30.0) -> dict[str, Any]:
    repo = Path(repo).resolve()
    rows = [
        evaluate_project(p, repo=repo, run=run, timeout=timeout)
        for p in discover_projects(repo)
    ]
    gated = [r for r in rows if r["coverage_gated"]]
    ungated = [r for r in rows if not r["coverage_gated"]]
    passing = [r for r in rows if r["verdict"] == PASS]
    for row in passing:
        if not row.get("thresholds_file"):
            raise RuntimeError(
                "a passing subtree must name the file whose enforcement "
                "command was executed"
            )
        if not row.get("has_thresholds_file"):
            raise RuntimeError("PASS without a thresholds file is the banned outcome")
    not_checked = sum(1 for r in rows if r["verdict"] == NOT_CHECKED)
    failed = sum(1 for r in rows if r["verdict"] == FAIL)
    return {
        "repo": str(repo),
        "project_count": len(rows),
        "gated_count": len(gated),
        "ungated_count": len(ungated),
        "pass_count": len(passing),
        "not_checked_count": not_checked,
        "fail_count": failed,
        "gated": [r["project"] for r in gated],
        "ungated": [r["project"] for r in ungated],
        "subtrees": rows,
        # aliases consumed by write_receipts.py
        "project_count": len(rows),
        "gated_count": len(gated),
        "ungated_count": len(ungated),
        "pass_count": len(passing),
        "not_checked_count": not_checked,
        "fail_count": failed,
        "subtrees": rows,
    }
