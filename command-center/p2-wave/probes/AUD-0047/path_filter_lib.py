#!/usr/bin/env python3
"""GitHub Actions path-filter evaluation helpers for AUD-0047."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


def load_workflow(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    # PyYAML parses unquoted `on:` as boolean True.
    if True in data and "on" not in data:
        data["on"] = data.pop(True)
    return data


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def extract_event_path_filters(on_block: Any) -> list[dict[str, Any]]:
    """Return per-event path filter records from a workflow `on:` block."""
    out: list[dict[str, Any]] = []
    if on_block is None:
        return out
    if isinstance(on_block, list):
        # on: [push, pull_request] — no path filters
        return out
    if isinstance(on_block, str):
        return out
    if not isinstance(on_block, dict):
        return out

    for event, cfg in on_block.items():
        event_name = str(event)
        if cfg is None or cfg is True or isinstance(cfg, list):
            continue
        if not isinstance(cfg, dict):
            continue
        paths = _as_list(cfg.get("paths"))
        paths_ignore = _as_list(cfg.get("paths-ignore"))
        if not paths and not paths_ignore:
            continue
        out.append(
            {
                "event": event_name,
                "paths": paths,
                "paths_ignore": paths_ignore,
            }
        )
    return out


def github_path_match(pattern: str, path: str) -> bool:
    """Approximate Actions path filter matching (glob / ** semantics)."""
    path = path.replace("\\", "/").lstrip("./")
    pattern = pattern.replace("\\", "/").strip()
    if not pattern:
        return False
    # trailing /** matches everything under prefix
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    # bare directory-ish patterns
    if pattern.endswith("/"):
        return path.startswith(pattern) or path.startswith(pattern.rstrip("/"))
    try:
        return PurePosixPath(path).match(pattern) or PurePosixPath(path).match(
            "**/" + pattern if not pattern.startswith("**/") else pattern
        )
    except ValueError:
        return False


def path_triggers_event(path: str, filt: dict[str, Any]) -> bool:
    """Return True if a change to `path` would trigger the event under filt."""
    paths = filt.get("paths") or []
    paths_ignore = filt.get("paths_ignore") or []
    if paths:
        included = any(github_path_match(p, path) for p in paths)
        if not included:
            return False
    if paths_ignore:
        if any(github_path_match(p, path) for p in paths_ignore):
            return False
    return True


_STEP_PATH_RE = re.compile(
    r"(?:python(?:3)?\s+-m\s+pytest\s+|python(?:3)?\s+|pwsh\s+-File\s+|bash\s+)"
    r"([^\s|&;]+)"
)
_EXPLICIT_FILE_RE = re.compile(
    r"\b((?:command-center|ci|tools|platform|scripts|\.quality)/[A-Za-z0-9_./\-]+\.(?:py|sh|yml|yaml|json|md))\b"
)


def infer_protected_files(workflow: dict[str, Any], workflow_path: Path) -> list[str]:
    """Heuristic protected-file set from job step commands + workflow path itself."""
    protected: set[str] = {workflow_path.as_posix()}
    jobs = workflow.get("jobs") or {}
    if not isinstance(jobs, dict):
        return sorted(protected)
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str):
                for m in _EXPLICIT_FILE_RE.finditer(run):
                    protected.add(m.group(1).replace("\\", "/"))
                for m in _STEP_PATH_RE.finditer(run):
                    token = m.group(1).strip("'\"")
                    if "/" in token and not token.startswith("-"):
                        protected.add(token.replace("\\", "/"))
            name = step.get("name")
            if isinstance(name, str):
                for m in _EXPLICIT_FILE_RE.finditer(name):
                    protected.add(m.group(1).replace("\\", "/"))
    return sorted(protected)


def evaluate_workflow(
    workflow_path: Path,
    *,
    protected_override: list[str] | None = None,
) -> dict[str, Any]:
    wf = load_workflow(workflow_path)
    filters = extract_event_path_filters(wf.get("on"))
    protected = protected_override or infer_protected_files(wf, workflow_path)
    holes: list[dict[str, Any]] = []
    for filt in filters:
        for pf in protected:
            if not path_triggers_event(pf, filt):
                holes.append(
                    {
                        "protected_file": pf,
                        "event": filt["event"],
                        "paths": filt["paths"],
                        "paths_ignore": filt["paths_ignore"],
                        "reason": (
                            "paths-ignore matches"
                            if any(
                                github_path_match(p, pf)
                                for p in (filt.get("paths_ignore") or [])
                            )
                            else "paths allowlist misses"
                        ),
                    }
                )
    return {
        "workflow": str(workflow_path).replace("\\", "/"),
        "has_path_filters": bool(filters),
        "filters": filters,
        "protected_files": protected,
        "hole_count": len(holes),
        "holes": holes,
    }
