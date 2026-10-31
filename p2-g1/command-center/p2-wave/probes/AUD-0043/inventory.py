"""Classify CI step command lines and local packaging entry points."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scenario import INVENTORY_REL, REPO

_PYTEST_M = re.compile(r"python(?:3)?\s+-m\s+pytest\b", re.I)
_BARE_PYTEST = re.compile(r"(?:^|[\s;&|])pytest\b", re.I)
_EDITABLE = re.compile(r"pip\s+install\s+-e\b", re.I)
_WHEEL_INSTALL = re.compile(
    r"pip\s+install\b[^\n]*(?:\.whl|dist/)", re.I
)
_CONSOLE_HINT = re.compile(
    r"(?:console.?script|project\.scripts|entry.?points)", re.I
)


def classify_command(cmd: str) -> list[str]:
    tags: list[str] = []
    if not cmd:
        return tags
    if _PYTEST_M.search(cmd):
        tags.append("python-m-pytest")
    if _BARE_PYTEST.search(cmd) and "python -m pytest" not in cmd.lower() and "python3 -m pytest" not in cmd.lower():
        tags.append("bare-pytest")
    if _EDITABLE.search(cmd):
        tags.append("editable-install")
    if _WHEEL_INSTALL.search(cmd):
        tags.append("wheel-artifact-install")
    if _CONSOLE_HINT.search(cmd):
        tags.append("console-script-mention")
    return tags


def census_inventory(path: Path | None = None) -> dict[str, Any]:
    inv_path = path or (REPO / INVENTORY_REL)
    present = inv_path.is_file()
    workflows_dir = REPO / ".github" / "workflows"
    rows: list[dict[str, Any]] = []
    counts = {
        "python-m-pytest": 0,
        "bare-pytest": 0,
        "editable-install": 0,
        "wheel-artifact-install": 0,
        "console-script-mention": 0,
        "steps": 0,
        "test_python_steps": 0,
    }
    if present:
        doc = json.loads(inv_path.read_text(encoding="utf-8"))
        for wf in doc.get("workflows") or []:
            if not isinstance(wf, dict):
                continue
            wf_file = str(wf.get("file") or "")
            for job in wf.get("jobs") or []:
                if not isinstance(job, dict):
                    continue
                job_id = str(job.get("job_id") or "")
                for step in job.get("steps") or []:
                    if not isinstance(step, dict):
                        continue
                    cmd = str(step.get("command") or "")
                    tags = classify_command(cmd)
                    counts["steps"] += 1
                    if job_id == "test-python":
                        counts["test_python_steps"] += 1
                    for tag in tags:
                        counts[tag] += 1
                    if tags:
                        rows.append(
                            {
                                "file": wf_file,
                                "job_id": job_id,
                                "step_index": step.get("index"),
                                "name": step.get("name"),
                                "tags": tags,
                                "command_head": cmd[:180],
                            }
                        )
    skip_dirs = {
        ".git",
        "node_modules",
        "venv",
        ".venv",
        "__pycache__",
        "dist",
        "build",
        ".tox",
        ".mypy_cache",
        "wheels",
        "site-packages",
    }
    scripts: list[dict[str, str]] = []
    for pyproject in sorted(REPO.rglob("pyproject.toml")):
        if any(part in skip_dirs for part in pyproject.parts):
            continue
        rel = pyproject.relative_to(REPO).as_posix()
        if "/probes/AUD-0043/" in f"/{rel}":
            continue
        text = pyproject.read_text(encoding="utf-8")
        has_scripts = "[project.scripts]" in text
        kind = "probe-fixture" if "/probes/" in f"/{rel}" else "production"
        scripts.append(
            {
                "path": rel,
                "has_project_scripts": str(has_scripts).lower(),
                "kind": kind,
            }
        )
    production_scripts = [
        row
        for row in scripts
        if row["has_project_scripts"] == "true" and row["kind"] == "production"
    ]
    probe_scripts = [
        row
        for row in scripts
        if row["has_project_scripts"] == "true" and row["kind"] == "probe-fixture"
    ]
    return {
        "inventory_path": INVENTORY_REL,
        "inventory_present": present,
        "github_workflows_present": workflows_dir.is_dir(),
        "counts": counts,
        "tagged_steps_sample": rows[:40],
        "pyproject_files": scripts,
        "production_project_scripts": production_scripts,
        "probe_fixture_project_scripts": probe_scripts,
        "ci_uses_installed_console_script": False,
        "ci_uses_source_or_editable_pytest": bool(
            counts["python-m-pytest"] or counts["bare-pytest"]
        ),
        "ci_uses_editable_install": bool(counts["editable-install"]),
        "ci_uses_wheel_artifact_install": bool(counts["wheel-artifact-install"]),
    }
