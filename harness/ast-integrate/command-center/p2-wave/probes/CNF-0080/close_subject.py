#!/usr/bin/env python3
"""Measure tools/command-center/close.py --dry-run versus a real --note run.

Predicted list is whatever the dry-run prints (it names no files).
Traced list is a filesystem census of a disposable catalog/graph/events trio.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fs_tracer as T  # noqa: E402

CLOSE = REPO / "tools/command-center/close.py"
TOOLS = REPO / "tools/command-center"


def _minimal_catalog() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "items": [
            {
                "id": "R-T01",
                "title": "cnf-0080 disposable",
                "program": "HARNESS",
                "section": "OUTSTANDING",
                "status": "OPEN",
                "disposition": None,
                "next_smallest_action": "touch the disposable catalog",
                "history": [],
            }
        ],
    }


def _run(root: Path, dry: bool) -> dict[str, Any]:
    catalog = root / "catalog.json"
    graph = root / "graph.json"
    events = root / "events.jsonl"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(TOOLS)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    cmd = [
        sys.executable,
        "-B",
        str(CLOSE),
        "R-T01",
        "--note",
        "cnf-0080-parity",
        "--catalog",
        str(catalog),
        "--graph",
        str(graph),
        "--events",
        str(events),
        "--now",
        "2026-08-24T18:00:00+00:00",
    ]
    if dry:
        cmd.append("--dry-run")
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        env=env,
        capture_output=True,
        text=True,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "cmd": cmd,
    }


def measure(tmp: Path) -> dict[str, Any]:
    dry_root = tmp / "dry"
    real_root = tmp / "real"
    for root in (dry_root, real_root):
        root.mkdir(parents=True)
        catalog = _minimal_catalog()
        (root / "catalog.json").write_text(
            json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (root / "graph.json").write_text("{}\n", encoding="utf-8")

    before_dry = T.census(dry_root)
    dry = _run(dry_root, dry=True)
    dry_actions = T.diff_census(before_dry, T.census(dry_root))

    before_real = T.census(real_root)
    real = _run(real_root, dry=False)
    real_actions = T.diff_census(before_real, T.census(real_root))

    predicted_from_stdout: list[dict[str, Any]] = []
    text = (dry["stdout"] + "\n" + dry["stderr"]).lower()
    # close.py dry-run prints a success line and names no mutation paths.
    predicted_omits_writes = not any(
        name in text for name in ("catalog.json", "graph.json", "events.jsonl")
    )
    destructive_missing = [
        a
        for a in real_actions
        if a["op"] in {"delete", "overwrite", "create"}
        and (a["op"], a["path"]) not in {(p.get("op"), p.get("path")) for p in predicted_from_stdout}
    ]
    return {
        "subject": "tools/command-center/close.py",
        "dry_exit": dry["exit_code"],
        "real_exit": real["exit_code"],
        "dry_stdout": dry["stdout"].strip(),
        "real_stdout": real["stdout"].strip(),
        "dry_stderr": dry["stderr"].strip()[:500],
        "real_stderr": real["stderr"].strip()[:500],
        "dry_run_wrote": dry_actions,
        "predicted_actions": predicted_from_stdout,
        "traced_actions": real_actions,
        "predicted_omits_mutation_paths": predicted_omits_writes,
        "dry_run_zero_writes": dry_actions == [],
        "understates": bool(destructive_missing) and predicted_omits_writes,
        "omitted_from_dry_run": destructive_missing,
    }
