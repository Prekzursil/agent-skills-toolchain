#!/usr/bin/env python3
"""T-9 terminal-state sweep - stuck `running` calls + non-terminal endings.

Defect (audit CS-2): 12% of recent sessions ended with tool calls stuck
`running` forever (67 stuck calls in each actual BOLT parent); interruption
mints new callIDs leaving originals running. Substrate: scripts/orphan_census.py
(read-only sqlite census over the live DB, bounded --limit, two-signal guard
in its docstring - the census is the standing measurement for this class).

Battery contract:
  1. DETECTOR CONTROL first: `orphan_census.py --self-test` (parser fixture,
     no db needed) must pass - a census that cannot parse orphan-shaped rows
     measures nothing.
  2. Live census: `--json <receipts>/t09_census.json --limit 50` (bounded;
     RAM discipline; output lands in the run's receipt dir so the anchor
     survives). The orphan COUNT is a recorded finding (hit), not a gate
     failure - the gate is "the sweep ran and produced a trustworthy number".
     Exit codes: 0 = ran, no orphans; 2 = ran, orphans found; 1 = error.

Both-states note: the NEGATIVE state (zero orphans) is only reachable after
the G-10 callID patch deploys; until then a non-zero count in the unpatched
binary is the expected positive state (see T-10 for that gate).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_common import (  # noqa: E402
    SCRIPTS, SUCCESS, FAILED, VerdictRecorder, py_run,
)

CENSUS = SCRIPTS / "orphan_census.py"


def run(rec: VerdictRecorder, opts: dict | None = None) -> str:
    opts = opts or {}
    limit = opts.get("limit", 50)
    if not CENSUS.is_file():
        rec.record("T-9", FAILED, reason="orphan_census.py missing",
                   anchors=[CENSUS])
        return FAILED

    ctrl = py_run(CENSUS, ["--self-test"])
    control_ok = ctrl.returncode == 0
    rec.hit("T-9", "detector_control", probe="--self-test",
            rc=ctrl.returncode, fires=control_ok,
            stdout_head=(ctrl.stdout or "")[:200])
    if not control_ok:
        rec.record("T-9", FAILED,
                   reason="self-test control did not pass - census untrusted",
                   anchors=[CENSUS])
        return FAILED

    out = rec.out_dir / "t09_census.json"   # durable: anchors must survive
    r = py_run(CENSUS, ["--json", str(out), "--limit", str(limit)],
               timeout=600)
    data = None
    if out.exists():
        try:
            data = json.loads(out.read_text(encoding="utf-8",
                                            errors="replace"))
        except json.JSONDecodeError:
            data = None
    if r.returncode not in (0, 2) or data is None:
        rec.record("T-9", FAILED,
                   reason=f"census did not run cleanly (rc={r.returncode})",
                   details={"stderr_head": (r.stderr or "")[:400],
                            "stdout_head": (r.stdout or "")[:400]},
                   anchors=[CENSUS])
        return FAILED

    total = data.get("stuck_calls_total")
    scanned = data.get("scanned")
    stuck_sessions = data.get("orphan_sessions")
    per_session = data.get("census") or []
    worst = max((s.get("stuck", 0) for s in per_session
                 if isinstance(s, dict)), default=0)
    rec.hit("T-9", "census", rc=r.returncode,
            sessions_scanned=scanned,
            sessions_with_stuck_calls=stuck_sessions,
            non_terminal_parts=total, worst_session_stuck=worst,
            parse_failures=data.get("parse_failures"))
    rec.record("T-9", SUCCESS,
               details={
                   "census_rc": r.returncode,
                   "note": "rc=2 means orphans found (expected pre-patch: "
                           "positive state of the CS-2 defect)",
                   "sessions_scanned": scanned,
                   "sessions_in_db": data.get("total_sessions_in_db"),
                   "sessions_with_stuck_calls": stuck_sessions,
                   "stuck_calls_total": total,
                   "worst_session_stuck": worst,
                   "two_signal_guard": (data.get("two_signal_guard") or "")[:120],
               },
               anchors=[CENSUS, out])
    return SUCCESS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()
    with VerdictRecorder(meta={"test": "T-9"}) as rec:
        status = run(rec, {"limit": args.limit})
        print(f"T-9 {status}")
        return 0 if status == SUCCESS else 1


if __name__ == "__main__":
    sys.exit(main())
