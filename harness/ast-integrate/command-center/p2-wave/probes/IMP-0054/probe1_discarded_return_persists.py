#!/usr/bin/env python3
"""Probe 1: discarded return value still produces a durable on-disk record.

Signal 1 of the catalog evidence requirement. The writer process ignores
the return handle; this probe, after that process has exited, reads the
JSONL sink from disk. In-process observation is not accepted as proof.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
MOD = PLUGIN / "degrade_loudly.py"
CODE = "IMP-0054.PROBE1.SWALLOWED"
MSG = "probe1 planted warning; return discarded"

sys.path.insert(0, str(PLUGIN))
import degrade_loudly as dl  # noqa: E402


def main() -> int:
    if not MOD.is_file():
        print("FAILED:IMP-0054-probe1 implementation missing")
        return 1
    import tempfile

    with tempfile.TemporaryDirectory(prefix="imp0054-p1-") as tmp:
        root = Path(tmp)
        env = os.environ.copy()
        env["PLUGIN_WARNING_SINK"] = str(root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        child = subprocess.run(
            [
                sys.executable,
                "-B",
                str(MOD),
                "discard-warn",
                "--sink",
                str(root),
                "--code",
                CODE,
                "--message",
                MSG,
            ],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        if child.returncode != 0:
            print("FAILED:IMP-0054-probe1 writer exit", child.returncode)
            print(child.stderr[-1500:])
            return 1
        if "discarded-return=true" not in child.stdout:
            print("FAILED:IMP-0054-probe1 writer did not discard")
            return 1
        # Child is dead. Proof is the file, not the return value.
        jsonl = root / "warnings.jsonl"
        if not jsonl.is_file():
            print("FAILED:IMP-0054-probe1 durable sink absent after writer exit")
            return 1
        body = jsonl.read_text(encoding="utf-8")
        recs = [json.loads(line) for line in body.splitlines() if line.strip()]
        if not any(r.get("code") == CODE and r.get("message") == MSG for r in recs):
            print("FAILED:IMP-0054-probe1 planted record missing from disk")
            print(body[:2000])
            return 1
        # Negative: a sibling empty sink has no such record.
        empty = Path(tmp) / "empty-sibling"
        empty.mkdir()
        empty_report = dl.Sink(dl.SinkConfig(directory=empty)).health_check()
        if empty_report["warnings_present"] or empty_report["verdict"] != "NO_WARNINGS":
            print("FAILED:IMP-0054-probe1 empty sibling was not explicit-empty")
            return 1

    out = {
        "probe": "probe1-discarded-return-persists",
        "unit_id": "IMP-0054",
        "writer_exit": child.returncode,
        "discarded_return": True,
        "durable_record_after_process_exit": True,
        "planted_code": CODE,
        "empty_sibling_explicit": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:IMP-0054-probe1 discarded return still persists on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
