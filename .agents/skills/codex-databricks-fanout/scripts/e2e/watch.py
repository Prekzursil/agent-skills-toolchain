"""Rich live monitor for a Databricks fan-out run — cluster phase, units-landed, throughput, ETA.
Usage: python e2e/watch.py <run_id> <dbfs_result_dir> [expected_n] [poll_s]
Example: python e2e/watch.py 710155915151427 dbfs:/tmp/E-preflight/results 1 15"""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.contract import RAIL

_TERMINAL = {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}


def sh(argv):
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return p.returncode, p.stdout, p.stderr


def fmt(sec):
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def count_landed(result_dir, prefix=""):
    """Count THIS run's landed artifacts. A prefix filter is essential — runs share a result dir,
    so a naive .md count double-counts stale sibling artifacts (measured: '2/1' for a 1-unit run)."""
    rc, out, _ = sh(
        ["databricks", "fs", "ls", result_dir, "--profile", RAIL["profile"]]
    )
    if rc != 0:
        return 0, []
    names = [
        ln.split("/")[-1].strip()
        for ln in out.splitlines()
        if ln.strip().endswith(".md") and ln.split("/")[-1].strip().startswith(prefix)
    ]
    return len(names), names


def main():
    run_id = sys.argv[1]
    result_dir = sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    poll_s = int(sys.argv[4]) if len(sys.argv) > 4 else 15
    label = sys.argv[5] if len(sys.argv) > 5 else run_id
    prefix = sys.argv[6] if len(sys.argv) > 6 else ""  # count only THIS run's artifacts

    t0 = time.time()
    last = -1
    while True:
        rc, out, _ = sh(
            ["databricks", "jobs", "get-run", run_id, "--profile", RAIL["profile"]]
        )
        state, msg = "?", ""
        try:
            st = json.loads(out).get("state") or {}
            state = st.get("life_cycle_state", "?")
            msg = (st.get("state_message", "") or "").strip()
        except json.JSONDecodeError:
            pass
        landed, names = count_landed(result_dir, prefix)
        el = time.time() - t0
        phase = (
            msg if msg else ("spinning up cluster" if state == "PENDING" else "in run")
        )
        pct = f" ({landed * 100 // n}%)" if n else ""
        rate = (landed / (el / 60)) if (el > 0 and landed) else 0
        eta = ""
        if n and 0 < landed < n:
            eta = f" · eta ~{fmt((n - landed) * (el / landed))}"
        elif n and landed == 0 and state == "RUNNING":
            eta = " · eta pending first unit"
        newly = ""
        if landed != last:
            newly = "  <- +" + str(landed - last) if last >= 0 and landed > last else ""
            last = landed
        print(
            f"[{label}] {state} · {phase[:48]} · {landed}/{n or '?'} landed{pct} · "
            f"{fmt(el)}{eta}" + (f" · {rate:.1f}/min" if rate else "") + newly,
            flush=True,
        )
        if state in _TERMINAL:
            print(
                f"[{label}] === TERMINAL {state} · {landed}/{n or '?'} landed · {fmt(el)} ==="
            )
            if names:
                print("[landed] " + ", ".join(sorted(names)))
            return 0 if state == "TERMINATED" else 1
        time.sleep(poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
