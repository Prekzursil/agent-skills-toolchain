r"""C2 -- why round 1's "wire-check = 33,938 ms / 135.8% of budget" could not be
reproduced, and what the honest claim is.

An independent verifier re-ran round 1's own `_h4_timing.py` and measured 11,590 ms
(46.4%) for the SAME check on the SAME tree -- a 2.9x disagreement. Round 1 published a
single point measurement as though it were a property of the hook.

HYPOTHESIS UNDER TEST
  H1  the number is noise -- repeated runs of the same hook on the same tree scatter
      widely with no explanation, so no timing claim about this hook is possible.
  H2  the number is a FUNCTION OF A MOVING INPUT -- wire-check resolves symbols out of
      the session's uncommitted diff, nine sibling lanes are writing to that tree
      continuously, and run time tracks the amount of work the diff implies. Then the
      point number is meaningless but the RELATIONSHIP is reproducible.

Discriminating measurement: run the hook N times and record, per run, both the wall time
AND the covariates that H2 says drive it -- how many changed files the hook decided to
examine, and how many ripgrep walks it launched. Under H1 the covariates stay flat while
the time scatters. Under H2 they move together.

DETECTOR CONTROLS (both must hold or the run is void):
  * counter-control: the _rg_lines wrapper must observe a NONZERO call count on at least
    one arm. A wrapper that never fires would report "0 rg calls" for every run and
    manufacture a flat covariate, i.e. fake evidence for H1.
  * arm-control: the live copy must NOT contain the encoding= fix and the repo copy MUST.
    Without this the two arms could silently be the same file.

Writes C2-TIMING-VARIANCE.json. Terminal marker per AGENTS.md 4.
"""

from __future__ import annotations

import argparse
import io
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
LIVE = Path("C:/Users/Prekzursil/.claude/hooks")
OUT = REPO / "command-center" / "hook-audit"
BUDGET_S = 25.0

# The thread-local stdio shims and the module loader already exist in the sibling probe
# and are imported rather than re-implemented (a dup-guard hook flagged the copy). That
# module is import-safe: everything it does at module scope is constant definitions, and
# its measurement is behind `if __name__ == "__main__"`.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _h4_timing import _TIn, _TOut, _tls, load as _load  # noqa: E402


def _one_run(path: Path, tag: str, idx: int, env: dict[str, str] | None = None) -> dict:
    """Load a fresh copy of the module, instrument it, call main() once.

    `env` is applied around the call and restored after, so a dose arm can swing the
    covariate on the SAME tree with the SAME code -- the only way to separate "time
    tracks the input" from "time is noise" without waiting for the tree to change.
    """
    import os

    saved = {k: os.environ.get(k) for k in (env or {})}
    for k, v in (env or {}).items():
        os.environ[k] = v
    mod = _load(path, f"c2_{tag}_{idx}")
    counters = {"rg_calls": 0, "changed_files": None, "rg_ms": 0.0}

    real_rg = getattr(mod, "_rg_lines", None)
    if real_rg is not None:

        def counting_rg(*a, **kw):
            counters["rg_calls"] += 1
            t = time.perf_counter()
            try:
                return real_rg(*a, **kw)
            finally:
                counters["rg_ms"] += (time.perf_counter() - t) * 1000.0

        mod._rg_lines = counting_rg

    real_cf = getattr(mod, "_changed_files", None)
    if real_cf is not None:

        def counting_cf(*a, **kw):
            r = real_cf(*a, **kw)
            try:
                counters["changed_files"] = len(r)
            except TypeError:
                pass
            return r

        mod._changed_files = counting_cf

    payload = json.dumps(
        {"session_id": "c2probe", "cwd": str(REPO), "stop_hook_active": False}
    )
    buf = io.StringIO()
    _tls.out, _tls.inp = buf, io.StringIO(payload)
    t0 = time.perf_counter()
    try:
        rc = mod.main()
    except BaseException as e:  # noqa: BLE001 - a crash is a datapoint
        rc = f"RUN-FAIL:{type(e).__name__}:{e}"
    ms = (time.perf_counter() - t0) * 1000.0
    _tls.out = _tls.inp = None
    emitted = buf.getvalue()
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    return {
        "arm": tag,
        "iteration": idx,
        "run_ms": round(ms, 1),
        "pct_of_25s_budget": round(100.0 * (ms / 1000.0) / BUDGET_S, 1),
        "rg_calls": counters["rg_calls"],
        "rg_ms": round(counters["rg_ms"], 1),
        "rg_share_pct": round(100.0 * counters["rg_ms"] / ms, 1) if ms else None,
        "changed_files_examined": counters["changed_files"],
        "rc": rc if isinstance(rc, str) else repr(rc),
        "emitted_bytes": len(emitted),
        "env": dict(env or {}),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()

    live_p = LIVE / "wire-check" / "check.py"
    repo_p = REPO / "hooks" / "wire-check" / "check.py"
    live_txt = live_p.read_text(encoding="utf-8", errors="replace")
    repo_txt = repo_p.read_text(encoding="utf-8", errors="replace")
    arm_control = {
        "live_has_encoding_fix": 'encoding="utf-8"' in live_txt,
        "repo_has_encoding_fix": 'encoding="utf-8"' in repo_txt,
        "must_be": "live False, repo True",
    }

    real_out, real_in = sys.stdout, sys.stdin
    sys.stdout, sys.stdin = _TOut(real_out), _TIn(real_in)
    runs = []
    try:
        for i in range(a.n):
            # Arms interleaved so a load spike cannot land on one arm only. The third
            # is the DOSE arm: same code, same tree, same per-walk cost -- only the
            # amount of input the hook admits changes (the F3 scratch skip is off).
            for tag, p, env in (
                ("live-unfixed", live_p, None),
                ("repo-fixed", repo_p, None),
                ("repo-fixed-DOSE-noskip", repo_p, {"WIRE_CHECK_NO_SKIP": "1"}),
            ):
                runs.append(_one_run(p, tag, i, env))
    finally:
        sys.stdout, sys.stdin = real_out, real_in

    by_arm: dict[str, list[dict]] = {}
    for r in runs:
        by_arm.setdefault(r["arm"], []).append(r)

    summary = {}
    for arm, rs in by_arm.items():
        ms = [r["run_ms"] for r in rs]
        summary[arm] = {
            "n": len(ms),
            "min_ms": round(min(ms), 1),
            "max_ms": round(max(ms), 1),
            "median_ms": round(statistics.median(ms), 1),
            "spread_ratio": round(max(ms) / min(ms), 2) if min(ms) else None,
            "min_pct": round(100.0 * min(ms) / 1000.0 / BUDGET_S, 1),
            "max_pct": round(100.0 * max(ms) / 1000.0 / BUDGET_S, 1),
            "rg_calls_min": min(r["rg_calls"] for r in rs),
            "rg_calls_max": max(r["rg_calls"] for r in rs),
            "changed_files": sorted(
                {r["changed_files_examined"] for r in rs}, key=lambda x: (x is None, x)
            ),
        }

    total_rg = sum(r["rg_calls"] for r in runs)
    counter_control_ok = total_rg > 0

    # H1 (noise) vs H2 (tracks a moving input), decided by the DOSE arm only. The two
    # observational arms cannot separate them: they differ in code as well as in input.
    base, dose = summary.get("repo-fixed"), summary.get("repo-fixed-DOSE-noskip")
    verdict = None
    if base and dose:
        cov_ratio = (
            (dose["rg_calls_max"] / base["rg_calls_max"])
            if base["rg_calls_max"]
            else None
        )
        time_ratio = (
            (dose["median_ms"] / base["median_ms"]) if base["median_ms"] else None
        )
        verdict = {
            "covariate_swing_x": round(cov_ratio, 2) if cov_ratio else None,
            "median_time_swing_x": round(time_ratio, 2) if time_ratio else None,
            "base_rg_calls": base["rg_calls_max"],
            "dose_rg_calls": dose["rg_calls_max"],
            "H2_supported": bool(
                cov_ratio and time_ratio and cov_ratio > 1.5 and time_ratio > 1.3
            ),
            "reading": (
                "H2: run time tracks the number of symbols the diff makes the hook "
                "resolve; a point measurement is not a property of the hook"
                if (cov_ratio and time_ratio and cov_ratio > 1.5 and time_ratio > 1.3)
                else "INCONCLUSIVE from this run -- covariate did not swing enough, "
                "or time did not follow it"
            ),
        }

    res = {
        "what": "wire-check run-time variance and its covariates",
        "budget_s": BUDGET_S,
        "arm_control": arm_control,
        "counter_control": {
            "total_rg_calls_observed": total_rg,
            "ok": counter_control_ok,
            "why": "a wrapper that never fires would report a flat covariate and fake H1",
        },
        "summary": summary,
        "dose_response_verdict": verdict,
        "runs": runs,
    }
    (OUT / "C2-TIMING-VARIANCE.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8"
    )

    print("== ARM CONTROL", arm_control)
    print("== COUNTER CONTROL total rg calls:", total_rg, "(must be > 0)")
    for arm, s in summary.items():
        print(
            f"{arm:14s} n={s['n']} min={s['min_ms']:9.1f} median={s['median_ms']:9.1f} "
            f"max={s['max_ms']:9.1f} ms  spread x{s['spread_ratio']}  "
            f"{s['min_pct']}%..{s['max_pct']}% of {BUDGET_S:.0f}s  "
            f"rg_calls={s['rg_calls_min']}..{s['rg_calls_max']} "
            f"changed_files={s['changed_files']}"
        )

    print("== DOSE RESPONSE (H1 noise vs H2 tracks-its-input):", verdict)
    if arm_control["live_has_encoding_fix"] or not arm_control["repo_has_encoding_fix"]:
        print("FAILED:c2-timing-variance arm control -- the two arms are not distinct")
        return 1
    if not counter_control_ok:
        print(
            "FAILED:c2-timing-variance counter control never fired -- covariates void"
        )
        return 1
    print("SUCCESS:c2-timing-variance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
