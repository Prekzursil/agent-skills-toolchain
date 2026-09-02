#!/usr/bin/env python3
"""Probe 2: later-process health-check, explicit empty sink, bounded rotation.

Signal 2 of the catalog evidence requirement (health-check in a separate
process) plus the reviewer check that the sink cannot grow without limit,
and the negative control that an empty sink is declared rather than silent.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
MOD = PLUGIN / "degrade_loudly.py"
CODE = "IMP-0054.PROBE2.PRIOR"

sys.path.insert(0, str(PLUGIN))
import degrade_loudly as dl  # noqa: E402


def run_mod(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-B", str(MOD), *args],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def main() -> int:
    if not MOD.is_file():
        print("FAILED:IMP-0054-probe2 implementation missing")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0054-p2-") as tmp:
        warned = Path(tmp) / "warned"
        empty = Path(tmp) / "empty"
        bounded = Path(tmp) / "bounded"
        unbounded = Path(tmp) / "unbounded"
        warned.mkdir()
        empty.mkdir()
        bounded.mkdir()
        unbounded.mkdir()

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        writer = run_mod(
            [
                "discard-warn",
                "--sink",
                str(warned),
                "--code",
                CODE,
                "--message",
                "prior process left this",
            ],
            env,
        )
        if writer.returncode != 0:
            print("FAILED:IMP-0054-probe2 writer", writer.stderr[-1500:])
            return 1

        # Separate process reads the sink the writer left behind.
        health = run_mod(["health", "--sink", str(warned)], env)
        if health.returncode != 0:
            print("FAILED:IMP-0054-probe2 health", health.stderr[-1500:])
            return 1
        report = json.loads(health.stdout.strip().splitlines()[-1])
        codes = [r.get("code") for r in report.get("records") or []]
        if report.get("verdict") != "WARNINGS_PRESENT" or CODE not in codes:
            print("FAILED:IMP-0054-probe2 health did not surface prior-process record")
            print(json.dumps(report, indent=2)[:2000])
            return 1
        if report.get("empty_sink") is True:
            print("FAILED:IMP-0054-probe2 warned sink claimed empty")
            return 1

        empty_health = run_mod(["health", "--sink", str(empty)], env)
        if empty_health.returncode != 0:
            print("FAILED:IMP-0054-probe2 empty health", empty_health.stderr[-1500:])
            return 1
        empty_report = json.loads(empty_health.stdout.strip().splitlines()[-1])
        if empty_report.get("verdict") != "NO_WARNINGS":
            print("FAILED:IMP-0054-probe2 empty verdict", empty_report.get("verdict"))
            return 1
        if empty_report.get("empty_sink_declared") is not True:
            print("FAILED:IMP-0054-probe2 empty sink was silent (not declared)")
            return 1
        if "no warnings" not in str(empty_report.get("explicit") or "").lower():
            print("FAILED:IMP-0054-probe2 empty explicit text missing")
            return 1
        if json.dumps(empty_report, sort_keys=True) == json.dumps(report, sort_keys=True):
            print("FAILED:IMP-0054-probe2 empty and warned health reports identical")
            return 1

        payload = "n" * 80
        bcfg = [
            "--max-file-bytes",
            "400",
            "--max-files",
            "3",
            "--hard-ceiling-bytes",
            "900",
        ]
        for i in range(40):
            w = run_mod(
                [
                    "warn",
                    "--sink",
                    str(bounded),
                    *bcfg,
                    "--code",
                    "IMP-0054.FLOOD",
                    "--message",
                    f"{payload}-{i}",
                ],
                env,
            )
            if w.returncode != 0:
                print("FAILED:IMP-0054-probe2 bounded write", w.stderr[-800:])
                return 1
        b_bytes = dl.Sink(
            dl.SinkConfig(
                directory=bounded,
                max_file_bytes=400,
                max_files=3,
                hard_ceiling_bytes=900,
            )
        ).total_bytes()
        b_files = len(list(bounded.glob("warnings.jsonl*")))
        if b_bytes > 900:
            print(f"FAILED:IMP-0054-probe2 bounded sink {b_bytes}B exceeds 900B ceiling")
            return 1
        if b_files > 3:
            print(f"FAILED:IMP-0054-probe2 file_count={b_files} exceeds max_files=3")
            return 1

        for i in range(40):
            w = run_mod(
                [
                    "warn",
                    "--sink",
                    str(unbounded),
                    *bcfg,
                    "--no-rotate",
                    "--code",
                    "IMP-0054.FLOOD",
                    "--message",
                    f"{payload}-{i}",
                ],
                env,
            )
            if w.returncode != 0:
                print("FAILED:IMP-0054-probe2 unbounded write", w.stderr[-800:])
                return 1
        u_bytes = dl.Sink(
            dl.SinkConfig(
                directory=unbounded,
                max_file_bytes=400,
                max_files=3,
                hard_ceiling_bytes=900,
                rotate=False,
            )
        ).total_bytes()
        if u_bytes <= 900:
            print(
                f"FAILED:IMP-0054-probe2 negative control: unbounded sink "
                f"{u_bytes}B did not exceed the 900B ceiling"
            )
            return 1

    out = {
        "probe": "probe2-health-and-bounds",
        "unit_id": "IMP-0054",
        "later_process_surfaced_prior_record": True,
        "empty_sink_explicit": True,
        "empty_and_warned_reports_differ": True,
        "bounded_bytes": b_bytes,
        "bounded_files": b_files,
        "unbounded_bytes": u_bytes,
        "ceiling_bytes": 900,
        "hard_ceiling_below_774kib_pathology": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0054-probe2 health-check surfaces sink; rotation is bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
