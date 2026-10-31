#!/usr/bin/env python3
"""Rich live monitor for a Databricks fan-out run — cluster phase, landed, throughput, ETA.

Watches ONE Databricks run and reports, every poll interval:
  cluster phase (PENDING spin-up vs RUNNING) · landed/total artifacts · elapsed · rate · ETA.

The landed count is PREFIX-FILTERED so a shared result dir's stale sibling artifacts are NOT
counted (the "2/1 landed" bug: a naive *.md count picked up a previous batch's files). Pass the
run's own prefix (e.g. "cov-env-inspector-") OR an explicit --expect-file of basenames, which
is exact-set matched and so is immune to a sibling whose name happens to share the prefix.

Usage (flag form):
    python e2e/watch.py --run-id 123456 --result-dir dbfs:/tmp/E-cov-env-inspector/results \\
        --prefix cov-env-inspector- --expect 12 --interval 30
    python e2e/watch.py --run-id 123456 --result-dir dbfs:/tmp/x/results \\
        --expect-file e2e/_E_x/expected.txt   # one basename per line

Usage (positional form — what the governed-run orchestrator template invokes):
    python e2e/watch.py <run_id> <result_dir> [expected_n] [poll_s] [label] [prefix]
    python e2e/watch.py 710155915151427 dbfs:/tmp/E-preflight/results 1 15

By default every poll prints a heartbeat line (silence is indistinguishable from a hung
monitor). --on-change reprints only when the landed count moves, plus the terminal line.

Read-only: it only calls `databricks jobs get-run` and `databricks fs ls`. Ctrl-C to stop.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness.contract import RAIL

# The rail contract is the single source of truth for the workspace profile; PROFILE_DEFAULT
# stays a module-level name so a caller can still override it per invocation via --profile.
PROFILE_DEFAULT = RAIL["profile"]
_TERMINAL = {"TERMINATED", "INTERNAL_ERROR", "SKIPPED"}


def sh(argv: list[str]) -> tuple[int, str, str]:
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return p.returncode, p.stdout, p.stderr


def fmt(sec: float) -> str:
    m, s = divmod(int(sec), 60)
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


# Pre-merge private aliases, kept so either historical call site still resolves.
_run = sh
_fmt = fmt


def run_state(
    run_id: str | int, profile: str = PROFILE_DEFAULT
) -> tuple[str, str, str]:
    """(life_cycle_state, result_state, state_message) for one run.

    result_state is load-bearing: a run can reach life_cycle_state=TERMINATED with
    result_state=FAILED, so lifecycle alone must never be read as success.
    Fails CLOSED — a `databricks jobs get-run` error or unparseable payload returns
    ("?", "", "") rather than a stale or optimistic reading.
    """
    rc, out, _ = sh(
        ["databricks", "jobs", "get-run", str(run_id), "--profile", profile]
    )
    if rc != 0:
        return "?", "", ""
    try:
        st = json.loads(out).get("state") or {}
    except json.JSONDecodeError:
        return "?", "", ""
    return (
        st.get("life_cycle_state", "?"),
        st.get("result_state", "") or "",
        (st.get("state_message", "") or "").strip(),
    )


_state = run_state


def count_landed(
    result_dir: str,
    prefix: str = "",
    expected: set[str] | None = None,
    profile: str = PROFILE_DEFAULT,
) -> tuple[int, list[str]]:
    """Count THIS run's landed artifacts; return (count, sorted basenames).

    A filter is essential — runs share a result dir, so a naive .md count double-counts stale
    sibling artifacts (measured: "2/1" for a 1-unit run). Precision order, best first:
      1. `expected` — exact basename set intersection.
      2. `prefix`   — basename prefix + .md suffix.
      3. neither    — every .md, which MAY over-count a shared dir's siblings.
    Fails CLOSED: a non-zero `databricks fs ls` returns (0, []), never a stale count.
    """
    rc, out, _ = sh(["databricks", "fs", "ls", result_dir, "--profile", profile])
    if rc != 0:
        return 0, []
    names = {ln.split("/")[-1].strip() for ln in out.splitlines() if ln.strip()}
    if expected:
        hit = sorted(expected & names)
    elif prefix:
        hit = sorted(n for n in names if n.startswith(prefix) and n.endswith(".md"))
    else:
        hit = sorted(n for n in names if n.endswith(".md"))
    return len(hit), hit


def watch(
    run_id: str | int,
    result_dir: str,
    total: int = 0,
    profile: str = PROFILE_DEFAULT,
    prefix: str | None = None,
    expected: set[str] | None = None,
    interval: int = 30,
    label: str | None = None,
    on_change: bool = False,
    out=sys.stdout,
) -> int:
    """Poll until the run reaches a terminal lifecycle state. 0 only on a full receipt."""
    label = label or f"watch {run_id}"
    t0 = time.time()
    last = -1
    while True:
        life, result, msg = run_state(run_id, profile)
        landed, names = count_landed(result_dir, prefix or "", expected, profile)
        el = time.time() - t0
        phase = msg or ("spinning up cluster" if life == "PENDING" else "in run")
        pct = f" ({landed * 100 // total}%)" if total else ""
        rate = (landed / (el / 60)) if (el > 0 and landed) else 0
        eta = ""
        if total and 0 < landed < total:
            eta = f" · eta ~{fmt((total - landed) * (el / landed))}"
        elif total and landed == 0 and life == "RUNNING":
            eta = " · eta pending first unit"
        newly = ""
        if landed != last:
            newly = f"  <- +{landed - last}" if last >= 0 and landed > last else ""
            last = landed
        elif on_change and life not in _TERMINAL:
            time.sleep(interval)
            continue
        print(
            f"[{label}] {life} · {phase[:48]} · {landed}/{total or '?'} landed{pct} · "
            f"{fmt(el)}{eta}" + (f" · {rate:.1f}/min" if rate else "") + newly,
            file=out,
            flush=True,
        )
        if life in _TERMINAL:
            print(
                f"[{label}] === TERMINAL {life}/{result or '?'} · "
                f"{landed}/{total or '?'} landed · {fmt(el)} ===",
                file=out,
                flush=True,
            )
            if names:
                print("[landed] " + ", ".join(names), file=out, flush=True)
            # Lifecycle TERMINATED is NOT success: require result_state SUCCESS *and*, when a
            # total is known, every artifact landed. Anything else is a failed receipt.
            return 0 if (result == "SUCCESS" and (not total or landed >= total)) else 1
        time.sleep(interval)


_POSITIONAL_USAGE = (
    "usage: watch.py <run_id> <result_dir> [expected_n] [poll_s] [label] [prefix]"
)


def _positional(argv: list[str]) -> argparse.Namespace:
    """Parse the positional call form. poll_s defaults to 15 here; the flag form uses 30."""

    def at(i, default=None):
        return argv[i] if len(argv) > i and argv[i] else default

    return argparse.Namespace(
        run_id=argv[0],
        result_dir=argv[1],
        expect=int(at(2, 0)),
        interval=int(at(3, 15)),
        label=at(4),
        prefix=at(5),
        expect_file=None,
        profile=PROFILE_DEFAULT,
        on_change=False,
    )


def _flags(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Live fan-out batch monitor")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--result-dir", required=True, help="dbfs:/... results dir")
    ap.add_argument("--expect", type=int, default=0, help="total units expected")
    ap.add_argument(
        "--prefix",
        default=None,
        help="artifact basename prefix filter (dedupes stale siblings)",
    )
    ap.add_argument(
        "--expect-file",
        default=None,
        help="file of expected basenames, one per line (exact-set match)",
    )
    ap.add_argument("--profile", default=PROFILE_DEFAULT)
    ap.add_argument("--interval", type=int, default=30)
    ap.add_argument(
        "--label", default=None, help="display label (default: 'watch <run_id>')"
    )
    ap.add_argument(
        "--on-change",
        action="store_true",
        help="print only when the landed count changes (default: every poll)",
    )
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and not argv[0].startswith("-"):
        if len(argv) < 2:
            print(_POSITIONAL_USAGE, file=sys.stderr)
            return 2
        a = _positional(argv)
    else:
        a = _flags(argv)
    expected = None
    if a.expect_file:
        expected = {
            ln.strip()
            for ln in Path(a.expect_file).read_text(encoding="utf-8").splitlines()
            if ln.strip()
        }
    total = a.expect or (len(expected) if expected else 0)
    return watch(
        a.run_id,
        a.result_dir,
        total,
        a.profile,
        a.prefix,
        expected,
        a.interval,
        a.label,
        a.on_change,
    )


if __name__ == "__main__":
    raise SystemExit(main())
