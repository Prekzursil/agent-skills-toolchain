"""Extract CI-pinned tool versions from the AUD-0041 workflow inventory.

This worktree has no .github/workflows/; the inventory is the captured
workflow text. Pin tuples only — secret-bearing command bodies are not copied.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INVENTORY = (
    REPO
    / "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json"
)

PIN_EQ = re.compile(
    r"\b(?:pip install(?:\s+-g)?\s+)?([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9][A-Za-z0-9.+]*)"
)
NPM_AT = re.compile(r"npm install -g (@[A-Za-z0-9_./-]+|@?[A-Za-z0-9_./-]+)@([0-9][0-9.]+)")
USES_SHA = re.compile(r"uses:([^@\s]+)@([0-9a-f]{40})")
GITLEAKS_V = re.compile(r"\bV=([0-9]+\.[0-9]+\.[0-9]+)\b")
UNEXPANDED = re.compile(r"\$\{GITLEAKS_VERSION\}")


def _commands(doc: object) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if not isinstance(doc, dict):
        return rows
    for wf in doc.get("workflows") or []:
        if not isinstance(wf, dict):
            continue
        file = str(wf.get("file") or "unknown.yml")
        for job in wf.get("jobs") or []:
            if not isinstance(job, dict):
                continue
            for step in job.get("steps") or []:
                if not isinstance(step, dict):
                    continue
                cmd = step.get("command")
                if isinstance(cmd, str) and cmd.strip():
                    rows.append((file, cmd))
    return rows


def extract_pins() -> list[dict]:
    pins: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    workflows_dir = REPO / ".github" / "workflows"
    pins.append(
        {
            "tool": ".github/workflows",
            "ci_pin": "present" if workflows_dir.is_dir() else "ABSENT-FROM-WORKTREE",
            "source": "worktree stat of .github/workflows",
            "kind": "tree",
            "version_sensitive_baseline": False,
        }
    )
    if not INVENTORY.is_file():
        pins.append(
            {
                "tool": "AUD-0041-inventory",
                "ci_pin": None,
                "source": str(INVENTORY.relative_to(REPO)),
                "kind": "missing-inventory",
                "version_sensitive_baseline": False,
            }
        )
        return pins
    doc = json.loads(INVENTORY.read_text(encoding="utf-8"))
    saw_unexpanded_gitleaks = False
    for file, cmd in _commands(doc):
        if UNEXPANDED.search(cmd):
            saw_unexpanded_gitleaks = True
        for name, ver in PIN_EQ.findall(cmd):
            if name.lower() in {"python", "pip"}:
                continue
            key = (name, ver, file)
            if key in seen:
                continue
            seen.add(key)
            pins.append(
                {
                    "tool": name,
                    "ci_pin": ver,
                    "source": f"{file} pip-style {name}=={ver}",
                    "kind": "pip-pin",
                    "version_sensitive_baseline": name.lower()
                    in {"ruff", "basedpyright", "black", "isort"},
                }
            )
        for name, ver in NPM_AT.findall(cmd):
            key = (name, ver, file)
            if key in seen:
                continue
            seen.add(key)
            pins.append(
                {
                    "tool": name,
                    "ci_pin": ver,
                    "source": f"{file} npm {name}@{ver}",
                    "kind": "npm-pin",
                    "version_sensitive_baseline": False,
                }
            )
        for action, sha in USES_SHA.findall(cmd):
            key = (action, sha[:12], file)
            if key in seen:
                continue
            seen.add(key)
            pins.append(
                {
                    "tool": action,
                    "ci_pin": sha,
                    "source": f"{file} uses {action}@{sha}",
                    "kind": "action-sha",
                    "version_sensitive_baseline": "gitleaks" in action
                    or "osv-scanner" in action,
                }
            )
        if "gitleaks" in cmd.lower() and GITLEAKS_V.search(cmd):
            ver = GITLEAKS_V.search(cmd).group(1)
            key = ("gitleaks", ver, file)
            if key not in seen:
                seen.add(key)
                pins.append(
                    {
                        "tool": "gitleaks",
                        "ci_pin": ver,
                        "source": f"{file} V={ver} gitleaks tarball",
                        "kind": "tarball-pin",
                        "version_sensitive_baseline": True,
                    }
                )
    if saw_unexpanded_gitleaks:
        pins.append(
            {
                "tool": "gitleaks",
                "ci_pin": None,
                "source": (
                    ".github/workflows/quality.yml gate-secrets uses "
                    "${GITLEAKS_VERSION}/${GITLEAKS_SHA256} which AUD-0041 did not "
                    "expand — missing-pin finding"
                ),
                "kind": "missing-pin",
                "version_sensitive_baseline": True,
            }
        )
    return pins
