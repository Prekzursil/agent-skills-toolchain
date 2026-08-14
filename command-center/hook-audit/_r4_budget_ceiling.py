#!/usr/bin/env python3
r"""_r4_budget_ceiling.py -- a per-check budget larger than its EVENT budget is not a
budget, it is a number in a file.

WHAT THIS SETTLES. Round 2 raised `git-hygiene` from 30 s to 90 s after it was disarmed
twice for taking 28,275 ms. Round 3's verifier then CONFIRMED that the timing row for it
is the throttled early return, and re-measured the guarded path at 18.7 s -- "20.7% of the
CURRENT 90 s budget, i.e. NOT over budget". That denominator is the thing this probe
questions.

THE MECHANISM, read out of the code rather than assumed:

  * `hooks/_dispatch/dispatch.py:349-370` starts one thread per check and joins them with
    `remaining = max(0.0, budget - (time.monotonic() - start))`. All threads share one
    `start`, so that arithmetic is CORRECT per check -- I checked this before claiming a
    defect and there is none there.
  * But the dispatcher is itself ONE command the harness runs with the EVENT's timeout.
    When the event timeout expires the harness kills the dispatcher process. `_receipt(...,
    "timeout")` never runs, because the code that would write it is dead with everything
    else. So the loss is not "the slow check is dropped", it is "every check on that event
    loses its output".

Therefore the enforceable ceiling for check i is `min(check_budget_i, event_budget)`, and a
check whose declared budget EXCEEDS its event budget can never spend it. This probe reports
every such pair from the committed manifest and from the live settings.json, so the claim is
arithmetic over real config, not an inference.

DETECTOR CONTROLS (both states, and they must DISCRIMINATE):
  * a synthetic manifest with a 90 s check inside a 35 s event MUST be flagged;
  * a synthetic manifest with a 5 s check inside a 35 s event MUST NOT be flagged;
  * `events[ev]` is a DICT whose hooks live under `checks` -- iterating the dict yields three
    key names and reports a false parity. The reader counts the CHECKS it actually compared
    and fails closed below a floor, so a shape change is loud instead of silently clean.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from _evidence_io import write_evidence

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
LIVE = Path(os.path.expanduser("~")) / ".claude"

MIN_CHECKS = 20  # live manifest holds 25; fail closed well under that


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def scan_manifest(man: dict) -> tuple[list[dict], int, int]:
    """-> (violations, checks_compared, events_seen). Reads events[ev]['checks'] as a LIST."""
    viol, n_checks, n_events = [], 0, 0
    for ev, body in (man.get("events") or {}).items():
        if not isinstance(body, dict):
            continue
        checks = body.get("checks")
        if not isinstance(checks, list):
            continue
        n_events += 1
        ev_budget = body.get("settings_timeout")
        for i, c in enumerate(checks):
            if not isinstance(c, dict):
                continue
            n_checks += 1
            cb = c.get("timeout")
            if not isinstance(cb, (int, float)) or not isinstance(
                ev_budget, (int, float)
            ):
                continue
            if cb >= ev_budget:
                viol.append(
                    {
                        "event": ev,
                        "join_index": i,
                        "check": c.get("name") or c.get("script"),
                        "check_budget_s": cb,
                        "event_budget_s": ev_budget,
                        "kind": "EXCEEDS" if cb > ev_budget else "EQUALS",
                        "unreachable_s": round(float(cb) - float(ev_budget), 1),
                    }
                )
    return viol, n_checks, n_events


def _synthetic(check_budget: float) -> dict:
    return {
        "events": {
            "Stop": {
                "settings_timeout": 35,
                "checks": [{"name": "synthetic", "timeout": check_budget}],
            }
        }
    }


def main() -> int:
    out: dict = {"probe": "_r4_budget_ceiling.py", "min_checks_floor": MIN_CHECKS}

    # --- detector controls first: a probe that has not proven it can fire measures nothing.
    hot, _, _ = scan_manifest(_synthetic(90))
    cold, _, _ = scan_manifest(_synthetic(5))
    out["control_broken_state_flags"] = len(hot)
    out["control_clean_state_flags"] = len(cold)
    out["controls_discriminate"] = len(hot) == 1 and len(cold) == 0
    if not out["controls_discriminate"]:
        # Not the committed file -- see `_evidence_io`. At this point `out` holds only the
        # two control counts, so writing it here would drop every measured key.
        where = write_evidence(HERE / "R4-BUDGET-CEILING.json", out, ok=False)
        print(json.dumps(out, indent=1))
        print(
            "FAILED:r4-budget-ceiling controls do not discriminate; verdict withheld; "
            f"partial output -> {where.name}"
        )
        return 1

    for label, path in (
        ("repo", REPO / "hooks" / "_dispatch" / "manifest.json"),
        ("live", LIVE / "hooks" / "_dispatch" / "manifest.json"),
    ):
        man = load(path)
        if man is None:
            out[label] = {"unreadable": str(path)}
            continue
        viol, n_checks, n_events = scan_manifest(man)
        out[label] = {
            "checks_compared": n_checks,
            "events_compared": n_events,
            "violations": viol,
        }

    # Fail closed on an implausible count -- "0 violations across 3 checks" is a shape bug.
    counts = [
        out[k]["checks_compared"]
        for k in ("repo", "live")
        if "checks_compared" in out.get(k, {})
    ]
    out["fail_closed_ok"] = bool(counts) and min(counts) >= MIN_CHECKS
    if not out["fail_closed_ok"]:
        write_evidence(HERE / "R4-BUDGET-CEILING.json", out, ok=False)
        print(json.dumps(out, indent=1))
        print(
            f"FAILED:r4-budget-ceiling compared {counts} checks, floor is {MIN_CHECKS} -- "
            "refusing to report parity from a collection I may have read at the wrong level"
        )
        return 1

    out["repo_violation_count"] = len(out["repo"]["violations"])
    out["live_violation_count"] = len(out["live"]["violations"])
    write_evidence(HERE / "R4-BUDGET-CEILING.json", out, ok=True)
    print(json.dumps(out, indent=1))
    print("SUCCESS:r4-budget-ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
