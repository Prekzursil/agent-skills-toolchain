#!/usr/bin/env python3
"""Probe 2: identical workflows compared to themselves produce a zero effect.

Sanity/control: the same workflow object on a powered matched case set must
archive per-case delta=0, raw mean delta=0, Cohen's dz=0, verdict=ZERO_EFFECT.
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
    run_paired_ab,
)

from scenario import WF_LEN, powered_cases  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0197.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0197-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:IMP-0197" not in json.dumps(doc):
        print("FAILED:IMP-0197-probe2 sentinel absent")
        return 1

    cases = powered_cases()
    live = run_paired_ab(WF_LEN, WF_LEN, cases)
    if live.get("n") != len(cases) or live.get("n") < DEFAULT_MIN_N:
        print("FAILED:IMP-0197-probe2 n", live.get("n"))
        return 1
    if live.get("status") != "POWERED":
        print("FAILED:IMP-0197-probe2 status", live.get("status"))
        return 1
    if live.get("verdict") != "ZERO_EFFECT":
        print("FAILED:IMP-0197-probe2 verdict", live.get("verdict"))
        return 1
    rows = live.get("paired_deltas") or []
    if len(rows) != len(cases):
        print("FAILED:IMP-0197-probe2 archived row count", len(rows))
        return 1
    if any(abs(float(r["delta"])) > 1e-12 for r in rows):
        print("FAILED:IMP-0197-probe2 nonzero paired delta in self-compare")
        return 1
    raw = (live.get("effect_size") or {}).get("raw_mean_delta")
    if raw is None or abs(float(raw)) > 1e-12:
        print("FAILED:IMP-0197-probe2 raw_mean_delta", raw)
        return 1
    dz = ((live.get("effect_size") or {}).get("cohens_dz") or {}).get("value")
    if dz is None or abs(float(dz)) > 1e-12:
        print("FAILED:IMP-0197-probe2 cohens_dz", dz)
        return 1
    if live.get("workflow_a_id") != live.get("workflow_b_id"):
        print("FAILED:IMP-0197-probe2 workflows not identical ids")
        return 1

    rec = doc.get("self_compare_run") or {}
    if rec.get("verdict") != "ZERO_EFFECT":
        print("FAILED:IMP-0197-probe2 receipt verdict", rec.get("verdict"))
        return 1
    if rec.get("paired_deltas") != rows:
        print("FAILED:IMP-0197-probe2 receipt self-compare deltas drifted from live")
        return 1
    rec_raw = (rec.get("effect_size") or {}).get("raw_mean_delta")
    if rec_raw is None or abs(float(rec_raw)) > 1e-12:
        print("FAILED:IMP-0197-probe2 receipt raw_mean_delta", rec_raw)
        return 1

    out = {
        "probe": "probe2-zero-effect",
        "unit_id": "IMP-0197",
        "n": live["n"],
        "verdict": live["verdict"],
        "raw_mean_delta": raw,
        "cohens_dz": dz,
        "all_deltas_zero": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"self-compare n={live['n']} verdict={live['verdict']} dz={dz}")
    print("SUCCESS:IMP-0197-probe2 identical workflows zero effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
