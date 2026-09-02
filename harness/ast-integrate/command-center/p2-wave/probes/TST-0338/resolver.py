#!/usr/bin/env python3
"""Per-project coverage-threshold resolver (TST-0338).

Thresholds and the enforcement command live in that project's
.coverage-thresholds.json, never in this module's memory. Locating the
file walks only the project root: a parent or sibling file is a different
project and must not be applied. Absence is NOT-CHECKED — never a silent
pass and never a block on a project that was never coverage-gated.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

THRESHOLDS_NAME = ".coverage-thresholds.json"
ABSENT = "NOT-CHECKED"
COMMAND_RAN = "COMMAND-RAN"
NO_COMMAND = "NO-COMMAND-DECLARED"
UNPARSEABLE = "UNPARSEABLE"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SKIP_PARTS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "runtime",
        ".tox",
        ".next",
        ".turbo",
        ".nx",
        "htmlcov",
        "coverage",
        "site-packages",
        "eggs",
    }
)
# Never a default command. Filling this from another project is the dead-command
# failure this unit names.
DEFAULT_ENFORCEMENT_COMMAND = None


def relpath(path: Path, root: Path | None = None) -> str:
    base = (root or REPO).resolve()
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(base).as_posix()
    except ValueError:
        return resolved.as_posix()


def locate_thresholds_file(project_root: Path) -> Path | None:
    """Return the project's own thresholds file, or None.

    Does not walk parents, does not search siblings, does not consult a
    hardcoded command. A file in a parent directory is another project's file.
    """
    root = Path(project_root).resolve()
    candidate = root / THRESHOLDS_NAME
    if candidate.is_file() and candidate.parent.resolve() == root:
        return candidate
    return None


def parse_thresholds(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError("thresholds file must be a JSON object")
    enforcement = doc.get("enforcement") if isinstance(doc.get("enforcement"), dict) else {}
    command = enforcement.get("command")
    if command is not None and not isinstance(command, str):
        command = None
    command = command.strip() if isinstance(command, str) else None
    if command == "":
        command = None
    return {
        "thresholds": doc.get("thresholds"),
        "enforcement": enforcement,
        "command": command,
        "blockPRCreation": enforcement.get("blockPRCreation"),
        "blockTaskCompletion": enforcement.get("blockTaskCompletion"),
    }


def run_declared_command(
    project_root: Path, command: str, *, timeout: int = 60
) -> dict[str, Any]:
    """Run *this* project's declared command in *this* project's cwd."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    root = Path(project_root).resolve()
    try:
        args = shlex.split(command, posix=os.name != "nt")
    except ValueError as exc:
        return {
            "command_run": command,
            "argv": [],
            "exit_code": 127,
            "output": f"unparseable command: {exc}",
        }
    if not args:
        return {
            "command_run": command,
            "argv": [],
            "exit_code": 127,
            "output": "empty command",
        }
    try:
        proc = subprocess.run(
            args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            encoding="utf-8",
            errors="replace",
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command_run": command,
            "argv": args,
            "exit_code": proc.returncode,
            "output": output,
        }
    except subprocess.TimeoutExpired:
        return {
            "command_run": command,
            "argv": args,
            "exit_code": 124,
            "output": f"TIMEOUT after {timeout}s: {command}",
        }
    except OSError as exc:
        return {
            "command_run": command,
            "argv": args,
            "exit_code": 127,
            "output": f"{type(exc).__name__}: {exc}",
        }


def evaluate_project(
    project_root: Path, *, timeout: int = 60, run_command: bool = True
) -> dict[str, Any]:
    """Resolve and, when a file exists, run that project's declared command.

    run_command=False is the live-tree census mode: report whether the file
    exists and which command it declares, without executing a third-party
    coverage tool. Fixture proofs always pass run_command=True.
    """
    root = Path(project_root).resolve()
    located = locate_thresholds_file(root)
    base = {
        "project": relpath(root),
        "file_exists": False,
        "file_path": None,
        "declared_command": None,
        "thresholds": None,
        "enforcement_ran": False,
        "exit_code": None,
        "output_tail": None,
        "pass": False,
        "blocked": False,
        "result": ABSENT,
        "reason": (
            "no .coverage-thresholds.json in this project root; absence is "
            "NOT-CHECKED, never a pass and never a block"
        ),
    }
    if located is None:
        return base
    base["file_exists"] = True
    base["file_path"] = relpath(located)
    try:
        parsed = parse_thresholds(located)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        base["result"] = UNPARSEABLE
        base["reason"] = f"thresholds file present but unparseable: {type(exc).__name__}: {exc}"
        return base
    base["thresholds"] = parsed.get("thresholds")
    command = parsed.get("command")
    base["declared_command"] = command
    if not command:
        base["result"] = NO_COMMAND
        base["reason"] = (
            "thresholds file exists but declares no enforcement.command; "
            "not a coverage pass"
        )
        return base
    if not run_command:
        base["result"] = "COMMAND-DECLARED"
        base["reason"] = (
            "thresholds file located and enforcement.command declared; live-tree "
            "census does not execute a third-party command (fixture proofs do)"
        )
        return base
    ran = run_declared_command(root, command, timeout=timeout)
    tail = ran.get("output") or ""
    base["enforcement_ran"] = True
    base["exit_code"] = ran.get("exit_code")
    base["output_tail"] = tail[-2000:]
    base["result"] = COMMAND_RAN
    base["argv"] = ran.get("argv")
    base["reason"] = (
        "declared enforcement command executed in this project root; exit code "
        "reported and not interpreted as a coverage pass"
    )
    return base


def discover_project_roots(repo: Path | None = None) -> list[Path]:
    """Marker-based discovery. Prunes skip dirs; does not walk other unit probes."""
    root = (repo or REPO).resolve()
    found: set[Path] = set()
    markers = (
        "pyproject.toml",
        "package.json",
        "pytest.ini",
        "setup.py",
        THRESHOLDS_NAME,
    )
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        current = Path(dirpath)
        if current.name == "probes" and current.parent.name == "p2-wave":
            dirnames[:] = []
            continue
        if any(name in filenames for name in markers):
            found.add(current.resolve())
    tools = root / "tools"
    if tools.is_dir():
        for child in tools.iterdir():
            if child.is_dir() and child.name not in SKIP_PARTS and not child.name.startswith("."):
                found.add(child.resolve())
    return sorted(found)


def evaluate_many(project_roots: list[Path], *, timeout: int = 60) -> list[dict[str, Any]]:
    """Per-project rows only. Callers must not average coverage numbers."""
    return [evaluate_project(p, timeout=timeout) for p in project_roots]


def find_ci_workflows(repo: Path | None = None) -> dict[str, Any]:
    root = (repo or REPO).resolve()
    paths: list[str] = []
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir():
        for p in sorted(wf_dir.iterdir()):
            if p.suffix.lower() in {".yml", ".yaml"} and p.is_file():
                paths.append(relpath(p, root))
    for name in ("azure-pipelines.yml", ".gitlab-ci.yml", "Jenkinsfile"):
        p = root / name
        if p.is_file():
            paths.append(relpath(p, root))
    if not paths:
        return {
            "exists": False,
            "paths": [],
            "result": ABSENT,
            "reason": "no CI workflow files declaring test steps were found on this worktree",
        }
    return {
        "exists": True,
        "paths": paths,
        "result": "FOUND",
        "reason": "paths listed; this resolver does not treat CI YAML as a thresholds file",
    }


def test_registry_status(repo: Path | None = None) -> dict[str, Any]:
    root = (repo or REPO).resolve()
    path = root / "command-center" / "TEST-REGISTRY.json"
    rel = "command-center/TEST-REGISTRY.json"
    if not path.is_file():
        return {
            "path": rel,
            "exists": False,
            "result": ABSENT,
            "reason": "TEST-REGISTRY.json is absent; not folded into a pass",
        }
    return {
        "path": rel,
        "exists": True,
        "result": "FOUND",
        "bytes": path.stat().st_size,
        "reason": "file present; TST-0338 does not treat the registry as a thresholds SSOT",
    }
