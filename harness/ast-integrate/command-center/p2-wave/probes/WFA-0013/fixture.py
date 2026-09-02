#!/usr/bin/env python3
"""Isolated git fixture for WFA-0013. Never stages into the host worktree."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gitutil import git, rev_parse

KNOWN_WORKFLOW = ".github/workflows/quality.yml"
KNOWN_NON_WORKFLOW = "README.md"
NEW_WORKFLOW_YAML = "tools/extra-gate.yml"
NEW_WORKFLOW_JSON = "tools/blueprints/planning/workflow.json"
AMBIGUOUS_YAML = "scripts/half.yml"
GHOST_REGISTRY_PATH = "tools/ghost-workflow.yml"
UNTRACKED_WORKFLOW = "untracked-workflow.yml"

QUALITY_YML = """name: quality
on:
  push:
  pull_request:
jobs:
  command-center:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""

EXTRA_GATE_YML = """name: extra-gate
on:
  workflow_dispatch:
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - run: echo gate
"""

HALF_YML = """# looks like a workflow but has no jobs
on:
  push:
"""

WORKFLOW_JSON = """{
  "id": "bp-eng-06.planning",
  "description": "Decompose a goal into verifiable steps.",
  "tools": ["Read", "Write"],
  "stop_rule": {"max_stages": 2, "on_error": "halt"},
  "stages": [
    {"id": "restate", "type": "task", "tools": ["Read"]},
    {"id": "gate", "type": "gate", "tools": ["Write"]}
  ]
}
"""

GHA_UNTRACKED = """name: should-not-enter
on:
  push:
jobs:
  x:
    runs-on: ubuntu-latest
    steps:
      - run: echo leaked
"""


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def registry_doc() -> dict[str, Any]:
    return {
        "artifact": "08-WORKFLOW-CANDIDATE-REGISTRY",
        "candidates": [
            {
                "id": "wf-repo-quality",
                "name": "quality.yml",
                "family": "B-repo-workflow",
                "provenance": KNOWN_WORKFLOW,
                "does": "CI quality gate",
                "mechanisms": ["gha"],
            },
            {
                "id": "wf-ghost-missing",
                "name": "ghost-workflow.yml",
                "family": "C-repo-tool",
                "provenance": GHOST_REGISTRY_PATH,
                "does": "registry row whose path is not in HEAD",
                "mechanisms": ["missing"],
            },
        ],
    }


def build_fixture(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    _write(root, KNOWN_WORKFLOW, QUALITY_YML)
    _write(root, KNOWN_NON_WORKFLOW, "fixture readme, not a workflow\n")
    _write(root, NEW_WORKFLOW_YAML, EXTRA_GATE_YML)
    _write(root, NEW_WORKFLOW_JSON, WORKFLOW_JSON)
    _write(root, AMBIGUOUS_YAML, HALF_YML)
    _write(root, "LICENSE", "permission text only\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "WFA-0013 fixture HEAD")
    _write(root, UNTRACKED_WORKFLOW, GHA_UNTRACKED)
    return {
        "head": rev_parse(root, "HEAD"),
        "registry": registry_doc(),
        "controls": [
            (KNOWN_WORKFLOW, "WORKFLOW"),
            (KNOWN_NON_WORKFLOW, "NON-WORKFLOW"),
        ],
        "untracked": UNTRACKED_WORKFLOW,
        "new_workflow_paths": [NEW_WORKFLOW_YAML, NEW_WORKFLOW_JSON],
        "ambiguous_path": AMBIGUOUS_YAML,
        "ghost_path": GHOST_REGISTRY_PATH,
        "known_workflow": KNOWN_WORKFLOW,
        "known_non_workflow": KNOWN_NON_WORKFLOW,
    }
