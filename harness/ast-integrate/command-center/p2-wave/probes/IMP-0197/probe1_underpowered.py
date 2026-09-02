#!/usr/bin/env python3
"""Probe 1: under-powered run returns INSUFFICIENT-EVIDENCE, never a verdict.

Both-states: the same A-better pair on 3 cases (n < min_n) must refuse a
verdict; on 24 cases (n >= min_n) it must emit A_BETTER. A runner that always
refuses, or that reports a percentage over three cases, fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.evals.paired_ab import (  # noqa: E402
    DEFAULT_MIN_N,
    INSUFFICIENT_EVIDENCE,
    VERDICTS,
    run_paired_ab,
)

from scenario import (  # noqa: E402
    WF_LEN,
    WF_PLUS,
    powered_cases,
    underpowered_cases,
)

ART = REPO / "command-center" / "receipts" / "IMP-0197.json"
WINNER_KEYS = ("verdict", "winner", "win_rate", "percent", "a_win_pct", "pct_a")


def _has_winner_verdict(result: dict) -> bool:
    if result.get("verdict") in VERDICTS:
        return True
    if result.get("winner") in ("A", "B", "A_BETTER", "B_BETTER"):
        return True
    for key in ("win_rate", "a_win_pct", "pct_a", "percent_a_wins"):
        if key in result and result.get("status") == INSUFFICIENT_EVIDENCE:
            return True
    return False


def _check_deltas(result: dict, cases: list) -> str | None:
    rows = result.get("paired_deltas")
    if not isinstance(rows, list) or len(rows) != len(cases):
        return f"paired_deltas n={0 if not isinstance(rows, list) else len(rows)} want={len(cases)}"
    ids = [r.get("case_id") for r in rows]
    want = [c["id"] for c in cases]
    if ids != want:
        return "paired_deltas case_id order mismatch (not the same case set)"
    for r in rows:
        if "delta" not in r or "score_a" not in r or "score_b" not in r:
            return "paired row missing score_a/score_b/delta"
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0197-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "IMP-0197":
        print("FAILED:IMP-0197-probe1 unit_id", doc.get("unit_id"))
        return 1
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0197" not in blob:
        print("FAILED:IMP-0197-probe1 sentinel absent")
        return 1

    # Exercise the module default (do not pass min_n) so a DEFAULT_MIN_N
    # mutation is visible. Catalog anti-pattern is a percentage over 3 cases.
    under_cases = underpowered_cases()
    power_cases = powered_cases()
    under = run_paired_ab(WF_PLUS, WF_LEN, under_cases)
    powered = run_paired_ab(WF_PLUS, WF_LEN, power_cases)

    if under.get("min_n") != DEFAULT_MIN_N:
        print("FAILED:IMP-0197-probe1 default min_n not exercised", under.get("min_n"))
        return 1
    if under.get("n") != len(under_cases) or under.get("n") >= DEFAULT_MIN_N:
        print("FAILED:IMP-0197-probe1 underpowered n", under.get("n"))
        return 1
    if under.get("status") != INSUFFICIENT_EVIDENCE:
        print("FAILED:IMP-0197-probe1 underpowered status", under.get("status"))
        return 1
    if under.get("verdict_refused") is not True:
        print("FAILED:IMP-0197-probe1 underpowered did not refuse verdict")
        return 1
    if _has_winner_verdict(under) or "verdict" in under:
        print("FAILED:IMP-0197-probe1 underpowered leaked a verdict", under)
        return 1
    err = _check_deltas(under, under_cases)
    if err:
        print("FAILED:IMP-0197-probe1 underpowered archive", err)
        return 1

    if powered.get("n") != len(power_cases) or powered.get("n") < DEFAULT_MIN_N:
        print("FAILED:IMP-0197-probe1 powered n", powered.get("n"))
        return 1
    if powered.get("status") != "POWERED":
        print("FAILED:IMP-0197-probe1 powered status", powered.get("status"))
        return 1
    if powered.get("verdict") != "A_BETTER":
        print("FAILED:IMP-0197-probe1 powered verdict", powered.get("verdict"))
        return 1
    if powered.get("verdict_refused") is not False:
        print("FAILED:IMP-0197-probe1 powered refused a valid verdict")
        return 1
    err = _check_deltas(powered, power_cases)
    if err:
        print("FAILED:IMP-0197-probe1 powered archive", err)
        return 1
    raw = (powered.get("effect_size") or {}).get("raw_mean_delta")
    if raw is None or abs(float(raw) - 1.0) > 1e-9:
        print("FAILED:IMP-0197-probe1 powered mean_delta", raw)
        return 1
    es = powered.get("effect_size") or {}
    if "n" not in es or int(es["n"]) != powered["n"]:
        print("FAILED:IMP-0197-probe1 effect_size missing n")
        return 1

    rec_under = doc.get("underpowered_run") or {}
    rec_power = doc.get("powered_run") or {}
    if rec_under.get("status") != INSUFFICIENT_EVIDENCE:
        print("FAILED:IMP-0197-probe1 receipt underpowered status", rec_under.get("status"))
        return 1
    if rec_under.get("verdict") in VERDICTS or "verdict" in rec_under:
        print("FAILED:IMP-0197-probe1 receipt underpowered leaked verdict")
        return 1
    if rec_power.get("verdict") != "A_BETTER":
        print("FAILED:IMP-0197-probe1 receipt powered verdict", rec_power.get("verdict"))
        return 1
    rec_rows = rec_under.get("paired_deltas") or []
    live_rows = under.get("paired_deltas") or []
    if rec_rows != live_rows:
        print("FAILED:IMP-0197-probe1 receipt underpowered deltas drifted from live")
        return 1
    rec_prows = rec_power.get("paired_deltas") or []
    live_prows = powered.get("paired_deltas") or []
    if rec_prows != live_prows:
        print("FAILED:IMP-0197-probe1 receipt powered deltas drifted from live")
        return 1

    out = {
        "probe": "probe1-underpowered",
        "unit_id": "IMP-0197",
        "underpowered_n": under["n"],
        "underpowered_status": under["status"],
        "underpowered_verdict_refused": True,
        "powered_n": powered["n"],
        "powered_verdict": powered["verdict"],
        "min_n": DEFAULT_MIN_N,
        "paired_deltas_archived": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"under n={under['n']} status={under['status']} refused={under['verdict_refused']} "
        f"powered n={powered['n']} verdict={powered['verdict']}"
    )
    print("SUCCESS:IMP-0197-probe1 under-powered INSUFFICIENT-EVIDENCE both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
