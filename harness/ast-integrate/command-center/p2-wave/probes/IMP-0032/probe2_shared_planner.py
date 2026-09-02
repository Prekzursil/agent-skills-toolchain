#!/usr/bin/env python3
"""Probe 2 (reviewer): dry-run shares plan_command with apply; CLI plan equals journal."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.inspect_planner import inspect_shared_planner  # noqa: E402
from plugin.mutations import fingerprints  # noqa: E402
from plugin.scenario import seed_home, write_payload  # noqa: E402


def run_cli(args: list[str]) -> tuple[int, dict, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(REPO / "tools") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, "-B", "-m", "plugin", *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    payload: dict = {}
    if proc.stdout:
        try:
            payload = json.loads(proc.stdout)
        except json.JSONDecodeError:
            payload = {}
    return proc.returncode, payload, text


def main() -> int:
    inspect = inspect_shared_planner(REPO)
    if not inspect.get("ok"):
        print("FAILED:IMP-0032-probe2 shared planner not confirmed")
        print(json.dumps(inspect, indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0032-p2-") as tmp:
        scratch = Path(tmp)
        home = seed_home(scratch / "home")
        source = write_payload(scratch, "1.0.0")
        journal_out = scratch / "journal.json"
        rc_dry, dry_payload, dry_text = run_cli(
            ["install", "--root", str(home), "--source", str(source), "--dry-run"]
        )
        if rc_dry != 0 or not dry_payload.get("dry_run"):
            print(f"FAILED:IMP-0032-probe2 dry-run cli rc={rc_dry} {dry_text[-1500:]}")
            return 1
        if dry_payload.get("applied"):
            print("FAILED:IMP-0032-probe2 dry-run claimed applied=true")
            return 1
        rc_real, real_payload, real_text = run_cli(
            [
                "install",
                "--root",
                str(home),
                "--source",
                str(source),
                "--journal-out",
                str(journal_out),
            ]
        )
        if rc_real != 0 or real_payload.get("dry_run"):
            print(f"FAILED:IMP-0032-probe2 real cli rc={rc_real} {real_text[-1500:]}")
            return 1
        if not journal_out.is_file():
            print("FAILED:IMP-0032-probe2 journal-out missing")
            return 1
        journal_doc = json.loads(journal_out.read_text(encoding="utf-8"))
        dry_fps = fingerprints(dry_payload.get("mutations") or [])
        journal_fps = fingerprints(journal_doc.get("journal") or [])
        real_fps = fingerprints(real_payload.get("journal") or [])
        if not dry_fps or dry_fps != journal_fps or dry_fps != real_fps:
            print("FAILED:IMP-0032-probe2 CLI dry-run plan != journal")
            print(json.dumps({"dry": dry_payload, "journal": journal_doc}, indent=2)[:4000])
            return 1

    summary = {
        "probe": "probe2-shared-planner",
        "unit_id": "IMP-0032",
        "shared_planner": inspect,
        "cli_dry_run_eq_journal": True,
        "dry_run_mutation_count": len(dry_payload.get("mutations") or []),
        "pass": True,
        "reviewer": {
            "reviewer_id": "IMP-0032-probe2-shared-planner",
            "verdict": "PASS",
            "independent": True,
            "finding": inspect["reason"],
        },
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"shared_planner=True cli_dry_run_eq_journal=True n={summary['dry_run_mutation_count']}"
    )
    print("SUCCESS:IMP-0032-probe2 dry-run shares plan_command; CLI plan equals journal")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
