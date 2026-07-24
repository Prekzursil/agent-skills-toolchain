#!/usr/bin/env python3
"""Standalone live monitor for a running fan-out batch (rich realtime progress).

Watches ONE Databricks run and reports, every --interval seconds:
  cluster phase (PENDING spin-up vs RUNNING) · landed/total artifacts · elapsed · ETA.

The landed count is PREFIX-FILTERED so a shared result dir's stale sibling artifacts are NOT
counted (the "2/1 landed" bug: a naive *.md count picked up a previous batch's files). Pass the
run's own --prefix (e.g. "cov-env-inspector-") OR an explicit --expect-file of basenames.

Usage:
    python e2e/watch.py --run-id 123456 --result-dir dbfs:/tmp/E-coverage-env-inspector/results \\
        --prefix cov-env-inspector- --expect 12 --interval 30
    python e2e/watch.py --run-id 123456 --result-dir dbfs:/tmp/x/results \\
        --expect-file e2e/_E_x/expected.txt   # one basename per line

Read-only: it only calls `databricks jobs get-run` and `databricks fs ls`. Ctrl-C to stop.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

PROFILE_DEFAULT = "bolt-datascience"
_TERMINAL = {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}


def _run(argv):
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120)
    return p.returncode, p.stdout, p.stderr


def _fmt(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def _state(run_id: str, profile: str) -> tuple[str, str, str]:
    rc, out, _ = _run(["databricks", "jobs", "get-run", str(run_id), "--profile", profile])
    if rc != 0:
        return "?", "", ""
    try:
        st = json.loads(out).get("state") or {}
    except json.JSONDecodeError:
        return "?", "", ""
    return (st.get("life_cycle_state", "?"),
            st.get("result_state", "") or "",
            (st.get("state_message", "") or "").strip())


def _landed(result_dir: str, profile: str, prefix: str | None, expected: set[str] | None) -> int:
    rc, out, _ = _run(["databricks", "fs", "ls", result_dir, "--profile", profile])
    if rc != 0:
        return 0
    names = {ln.split("/")[-1].strip() for ln in out.splitlines() if ln.strip()}
    if expected:
        return len(expected & names)
    if prefix:
        return sum(1 for n in names if n.startswith(prefix) and n.endswith(".md"))
    return sum(1 for n in names if n.endswith(".md"))   # last resort (may over-count siblings)


def watch(run_id, result_dir, total, profile=PROFILE_DEFAULT, prefix=None, expected=None,
          interval=30, out=sys.stdout) -> int:
    t0 = time.time()
    last = -1
    while True:
        life, result, msg = _state(run_id, profile)
        landed = _landed(result_dir, profile, prefix, expected)
        elapsed = time.time() - t0
        phase = msg[:48] if msg else ("spinning up cluster" if life == "PENDING" else "in run")
        eta = ""
        if 0 < landed < total:
            eta = f" · eta ~{_fmt((total - landed) * (elapsed / landed))}"
        bar = f"{landed}/{total}" if total else f"{landed}"
        line = f"[watch {run_id}] {life} · {phase} · {bar} landed · {_fmt(elapsed)}{eta}"
        if landed != last or life in _TERMINAL:   # only reprint on change or terminal
            print(line, file=out, flush=True)
            last = landed
        if life in _TERMINAL:
            print(f"[watch {run_id}] === terminal={life}/{result or '?'} · "
                  f"{landed}/{total} landed · {_fmt(elapsed)} ===", file=out, flush=True)
            return 0 if (result == "SUCCESS" and (not total or landed >= total)) else 1
        time.sleep(interval)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live fan-out batch monitor")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--result-dir", required=True, help="dbfs:/... results dir")
    ap.add_argument("--expect", type=int, default=0, help="total units expected")
    ap.add_argument("--prefix", default=None, help="artifact basename prefix filter (dedupes siblings)")
    ap.add_argument("--expect-file", default=None, help="file of expected basenames, one per line")
    ap.add_argument("--profile", default=PROFILE_DEFAULT)
    ap.add_argument("--interval", type=int, default=30)
    a = ap.parse_args(argv)
    expected = None
    if a.expect_file:
        expected = {ln.strip() for ln in Path(a.expect_file).read_text(encoding="utf-8").splitlines()
                    if ln.strip()}
    total = a.expect or (len(expected) if expected else 0)
    return watch(a.run_id, a.result_dir, total, a.profile, a.prefix, expected, a.interval)


if __name__ == "__main__":
    raise SystemExit(main())
