"""Shared fixture builder for IMP-0115 named probes."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TOOLS = REPO / "tools"
CLI = ["python3", "-B", "-m", "marketplace"]

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_PRECONDITION = 3
EXIT_VALIDATION = 4
EXIT_BLOCKED_NEEDS_OWNER = 10


def env() -> dict[str, str]:
    out = os.environ.copy()
    out["PYTHONPATH"] = str(TOOLS) + os.pathsep + out.get("PYTHONPATH", "")
    out["PYTHONDONTWRITEBYTECODE"] = "1"
    out["MARKETPLACE_RELEASE_MODE"] = "PR-ONLY"
    return out


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        CLI + args,
        cwd=str(cwd),
        env=env(),
        capture_output=True,
        text=True,
        timeout=60,
    )


def write_good_tree(root: Path) -> Path:
    src = root / "good-pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "manifest.json").write_text(
        json.dumps(
            {
                "name": "echo-skill",
                "version": "1.0.0",
                "license": "MIT",
                "permissions": ["fs:read"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (src / "README.md").write_text("# echo-skill\nA live probe fixture.\n", encoding="utf-8")
    return src


def write_bad_tree(root: Path) -> Path:
    src = root / "bad-pkg"
    src.mkdir(parents=True, exist_ok=True)
    (src / "manifest.json").write_text(
        json.dumps(
            {
                "name": "Echo_Skill",
                "version": "not-semver",
                "license": "Proprietary",
                "permissions": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (src / "leak.txt").write_text("AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8")
    return src


def write_empty_index(root: Path) -> Path:
    path = root / "index.json"
    path.write_text(
        json.dumps({"schema": "marketplace-index/v1", "packages": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path
