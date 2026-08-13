#!/usr/bin/env python3
r"""_r4_githygiene_range.py -- measure what `git-hygiene` costs when it actually RUNS, and
publish it as a RANGE against both denominators.

WHY. `H4-TIMING-live.json` records `Stop/git-hygiene run_ms=0.3, emitted_bytes=0,
pct_of_budget=0.0`. Round 3's verifier CONFIRMED that this row is not a measurement of the
check: `hooks/git-hygiene/check.py:1196-1207` returns 0 before doing any work when the
`.last-run` stamp is younger than `GIT_HYGIENE_THROTTLE_SEC` (default 900 s). The row is the
early return, understated by ~1e5x, and it is the row that let "all other 22 checks are
≤ 0.3% of budget" absorb the single most expensive check in the fleet.

WHAT THIS PROBE DOES DIFFERENTLY from the four prior samples: it does not touch the LIVE
throttle clock. `throttle > 0 and stamp.exists()` guards the early return, so exporting
`GIT_HYGIENE_THROTTLE_SEC=0` defeats it without deleting or back-dating a stamp. It runs the
REPO copy, whose `.last-run` is gitignored, so nothing outside this checkout changes and the
live 15-minute clock is left exactly as the session set it.

DENOMINATOR -- the correction this probe exists to make. Round 2 raised the check budget
30 s -> 90 s, and round 3 measured 18.7 s and called it "20.7% of the CURRENT 90 s budget,
NOT over budget". But 90 s is not reachable: the dispatcher is one command the harness runs
under the Stop EVENT timeout of 35 s (see `_r4_budget_ceiling.py` -- 55 s of that 90 s is
unreachable in both trees). So the honest statement carries BOTH percentages.

DETECTOR CONTROLS (both states, must DISCRIMINATE):
  * throttle-EFFECTIVE arm (fresh stamp, default throttle) must return fast and emit nothing;
  * throttle-DEFEATED arm (GIT_HYGIENE_THROTTLE_SEC=0) must take orders of magnitude longer;
  * `arms_discriminate` requires >= 100x between them. If they agree, the probe never
    defeated the throttle and it publishes INCONCLUSIVE rather than a number.
  * the repo stamp's bytes and mtime are captured before and restored after, then re-read
    and compared, so a failed restore is reported rather than assumed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CHECK = REPO / "hooks" / "git-hygiene" / "check.py"
STAMP = REPO / "hooks" / "git-hygiene" / ".last-run"

STOP_PAYLOAD = json.dumps(
    {"hook_event_name": "Stop", "session_id": "r4-githygiene-probe"}
)

# Prior samples, each from a different probe/agent, recorded so the RANGE is not one point.
PRIOR_SAMPLES_MS = {
    "round2_fix_hook_timeouts_note": 28275.0,
    "round3_verifier_arm_C": 18657.7,
    "round3_auditor_sample_a": 11800.0,
    "round3_auditor_sample_b": 32700.0,
}

CHECK_BUDGET_S = 90.0  # declared in hooks/_dispatch/manifest.json, Stop/git-hygiene
EVENT_BUDGET_S = 35.0  # Stop event settings_timeout -- the ENFORCED ceiling


def _run(defeat_throttle: bool) -> dict:
    env = dict(os.environ)
    if defeat_throttle:
        env["GIT_HYGIENE_THROTTLE_SEC"] = "0"
    else:
        env.pop("GIT_HYGIENE_THROTTLE_SEC", None)
    t0 = time.monotonic()
    p = subprocess.run(
        [sys.executable, str(CHECK)],
        input=STOP_PAYLOAD,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )
    ms = round((time.monotonic() - t0) * 1000, 1)
    return {
        "ms": ms,
        "rc": p.returncode,
        "stdout_bytes": len(p.stdout or ""),
        "stderr_bytes": len(p.stderr or ""),
    }


def main() -> int:
    out: dict = {"probe": "_r4_githygiene_range.py", "tree": "repo"}
    if not CHECK.is_file():
        print(f"FAILED:r4-githygiene repo check.py absent at {CHECK}")
        return 1

    had_stamp = STAMP.exists()
    stamp_bytes = STAMP.read_bytes() if had_stamp else None
    stamp_stat = STAMP.stat() if had_stamp else None

    try:
        # Arm A: throttle EFFECTIVE. Write a fresh stamp so the guard is certainly armed.
        STAMP.write_text(str(time.time()), encoding="utf-8")
        out["A_throttle_effective"] = _run(defeat_throttle=False)
        # Arm B: throttle DEFEATED via the env knob -- no stamp deletion, no back-dating.
        out["B_throttle_defeated"] = _run(defeat_throttle=True)
    finally:
        if had_stamp:
            STAMP.write_bytes(stamp_bytes)
            os.utime(STAMP, (stamp_stat.st_atime, stamp_stat.st_mtime))
            out["stamp_restored_exact"] = (
                STAMP.read_bytes() == stamp_bytes
                and abs(STAMP.stat().st_mtime - stamp_stat.st_mtime) < 1e-6
            )
        else:
            STAMP.unlink(missing_ok=True)
            out["stamp_restored_exact"] = not STAMP.exists()

    a = out["A_throttle_effective"]["ms"]
    b = out["B_throttle_defeated"]["ms"]
    out["ratio_defeated_over_effective"] = round(b / a, 1) if a > 0 else None
    out["arms_discriminate"] = bool(a > 0 and b / a >= 100)
    if not out["arms_discriminate"]:
        out["verdict"] = "INCONCLUSIVE"
        (HERE / "R4-GITHYGIENE-RANGE.json").write_text(
            json.dumps(out, indent=1), encoding="utf-8"
        )
        print(json.dumps(out, indent=1))
        print(
            "FAILED:r4-githygiene the two arms did not separate -- the throttle was probably "
            "never defeated, so no cost number here may be cited"
        )
        return 1

    samples = dict(PRIOR_SAMPLES_MS)
    samples["r4_this_probe_repo_copy"] = b
    lo, hi = min(samples.values()), max(samples.values())
    out["samples_ms"] = samples
    out["range_ms"] = [lo, hi]
    out["range_pct_of_declared_90s_check_budget"] = [
        round(lo / (CHECK_BUDGET_S * 10), 1),
        round(hi / (CHECK_BUDGET_S * 10), 1),
    ]
    out["range_pct_of_enforced_35s_event_budget"] = [
        round(lo / (EVENT_BUDGET_S * 10), 1),
        round(hi / (EVENT_BUDGET_S * 10), 1),
    ]
    out["h4_recorded_run_ms"] = 0.3
    out["understatement_factor_vs_h4"] = round(b / 0.3)
    out["verdict"] = "H4_ROW_IS_THE_EARLY_RETURN"
    (HERE / "R4-GITHYGIENE-RANGE.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8"
    )
    print(json.dumps(out, indent=1))
    print("SUCCESS:r4-githygiene")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
