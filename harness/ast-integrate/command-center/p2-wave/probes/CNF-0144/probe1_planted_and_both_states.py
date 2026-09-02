#!/usr/bin/env python3
"""Probe 1: planted 20% expensive drop must fire; unbiased sample must be silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convenience_bias as CB  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "CNF-0144.json"


def main() -> int:
    rows = CB.ensure_fixtures()
    unbiased = CB.analyze(rows)
    if not unbiased["silent"]:
        print("FAILED:CNF-0144-probe1 unbiased fixture fired (both-states broken)")
        print(json.dumps(unbiased["pearson"], sort_keys=True))
        return 1
    if unbiased["fires"] is True:
        print("FAILED:CNF-0144-probe1 unbiased fires=True")
        return 1
    planted_rows = CB.drop_expensive_completions(rows, CB.PLANTED_DROP_FRACTION)
    n_completed = sum(1 for r in rows if r.completed)
    n_planted = sum(1 for r in planted_rows if r.completed)
    dropped = n_completed - n_planted
    expected = max(1, int(n_completed * CB.PLANTED_DROP_FRACTION))
    if dropped != expected:
        print(f"FAILED:CNF-0144-probe1 drop count {dropped} != {expected}")
        return 1
    planted = CB.analyze(planted_rows)
    if not planted["fires"]:
        print("FAILED:CNF-0144-probe1 planted drop did not fire")
        print(json.dumps(planted["pearson"], sort_keys=True))
        return 1
    r = planted["pearson"]["r"]
    if r is None or r > -CB.MATERIAL_ABS_R:
        print(f"FAILED:CNF-0144-probe1 planted r={r} not material negative")
        return 1
    # Realised fixture (unbiased) CI must include 0 so a 'no bias' claim cites interval.
    ci = unbiased["pearson"]["ci95"]
    if ci["low"] is None or ci["high"] is None:
        print("FAILED:CNF-0144-probe1 unbiased CI missing")
        return 1
    if not (ci["low"] <= 0.0 <= ci["high"]):
        print(f"FAILED:CNF-0144-probe1 unbiased CI excludes 0: {ci}")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:CNF-0144-probe1 self-declared {doc.get('state')}")
            return 1
        if "SUCCESS:CNF-0144" not in text:
            print("FAILED:CNF-0144-probe1 sentinel-absent")
            return 1
        tests = {t.get("id"): t for t in doc.get("tests") or [] if isinstance(t, dict)}
        for tid in ("planted-control", "both-states"):
            if tests.get(tid, {}).get("result") != "PASS":
                print(f"FAILED:CNF-0144-probe1 artifact test {tid} not PASS")
                return 1
    out = {
        "probe": "probe1-planted-and-both-states",
        "unit_id": "CNF-0144",
        "unbiased_silent": True,
        "unbiased_r": unbiased["pearson"]["r"],
        "unbiased_p": unbiased["pearson"]["p_value"],
        "unbiased_ci95": unbiased["pearson"]["ci95"],
        "planted_fires": True,
        "planted_r": planted["pearson"]["r"],
        "planted_p": planted["pearson"]["p_value"],
        "planted_n": planted["n"],
        "dropped": dropped,
        "expected_drop": expected,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"unbiased_silent=True planted_fires=True dropped={dropped}/{n_completed} "
        f"r_unbiased={unbiased['pearson']['r']:.4f} r_planted={planted['pearson']['r']:.4f}"
    )
    print("SUCCESS:CNF-0144-probe1 planted control and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
