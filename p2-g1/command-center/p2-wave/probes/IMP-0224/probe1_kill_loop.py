"""IMP-0224 probe 1 (source): 50 kill-loop iterations leave parseable published ledgers.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0224/probe1_kill_loop.py
Each iteration seeds a ledger, starts a chunked staging write and SIGKILLs the writer
mid-flight. The published path must keep the partial record ABSENT (staging leftover
ignored) and parse fully - measured 50 times, never reasoned about.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

W = Path(__file__).resolve().parents[4]
KILL_TARGET = W / "tools" / "event-ledger" / "kill_target.py"


def one_iteration(root: Path, i: int) -> dict:
    dest = root / ("ledger-%03d.jsonl" % i)
    seed = {"seq": 1, "ts": "2026-10-25T00:00:00", "kind": "note", "text": "seed"}
    dest.write_text(json.dumps(seed) + "\n", encoding="utf-8")
    staging = dest.with_name(dest.name + ".staging")
    proc = subprocess.Popen(
        [
            sys.executable, "-B", str(KILL_TARGET),
            "--path", str(dest),
            "--payload-bytes", "4096",
            "--chunk-size", "128",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    saw_staging = False
    deadline = time.time() + 5.0
    while time.time() < deadline:
        try:
            if staging.exists() and staging.stat().st_size > 0:
                saw_staging = True
                break
        except OSError:
            pass
        time.sleep(0.002)
    killed = False
    if proc.poll() is None:
        try:
            os.kill(proc.pid, signal.SIGTERM)
            killed = True
        except OSError:
            killed = False
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    raw = dest.read_bytes() if dest.exists() else b""
    lines = [ln for ln in raw.decode("utf-8", errors="replace").splitlines() if ln.strip()]
    parseable = True
    for ln in lines:
        try:
            json.loads(ln)
        except Exception:
            parseable = False
    staging_left = 1 if staging.exists() else 0
    return {
        "iteration": i,
        "saw_staging": saw_staging,
        "killed": killed,
        "rc": proc.returncode,
        "line_count": len(lines),
        "parseable": parseable,
        "staging_left": staging_left,
    }


def main() -> int:
    iterations = 50
    samples = []
    parseable_ledgers = 0
    half_written_total = 0
    interrupted_staging = 0
    replaced_clean = 0
    with tempfile.TemporaryDirectory(prefix="imp0224-") as td:
        root = Path(td)
        for i in range(iterations):
            row = one_iteration(root, i)
            if row["saw_staging"] and row["staging_left"]:
                interrupted_staging += 1
            if row["parseable"]:
                parseable_ledgers += 1
            else:
                half_written_total += 1
            if row["parseable"] and row["line_count"] == 2 and not row["staging_left"]:
                replaced_clean += 1
            if i < 3:
                samples.append(row)
    doc = {
        "unit_id": "IMP-0224",
        "probe": "probe1-kill-loop",
        "iterations": iterations,
        "parseable_ledgers": parseable_ledgers,
        "half_written_total": half_written_total,
        "interrupted_staging_observed": interrupted_staging,
        "replaced_clean": replaced_clean,
        "sample": samples,
        "pass": parseable_ledgers == iterations and half_written_total == 0,
    }
    out = Path(__file__).resolve().parent / "probe1-kill.raw.json"
    out.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps(doc, sort_keys=True))
    print("parseable=%d/%d half_written=%d staging_hits=%d"
          % (parseable_ledgers, iterations, half_written_total, interrupted_staging))
    if doc["pass"]:
        print("SUCCESS:IMP-0224-probe1 kill-loop ledgers all parseable; partial records"
              " absent from the published path")
        return 0
    print("FAILED:IMP-0224-probe1 torn or truncated published ledger observed")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
