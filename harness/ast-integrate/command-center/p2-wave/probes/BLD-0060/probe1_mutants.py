#!/usr/bin/env python3
"""Named probe 1: planted-mutant firing rates and precision/recall at n=100 and n=20480."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import model as M  # noqa: E402

ART = REPO / "command-center/receipts/BLD-0060.json"
EPS = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0060-probe1 {msg}")
    return 1


def close(a, b) -> bool:
    if a is None or b is None:
        return a == b
    return abs(float(a) - float(b)) <= EPS


def check_scale(label: str, live, rec_scale: dict) -> str | None:
    got = M.measure_scale(live, int(rec_scale["n"]), M.THRESHOLD)
    if got["n"] != rec_scale["n"]:
        return f"{label} n {got['n']}!={rec_scale['n']}"
    if got["pair_count"] != rec_scale["pair_count"]:
        return f"{label} pair_count {got['pair_count']}!={rec_scale['pair_count']}"
    if not close(got["clean_max_jaccard"], rec_scale["clean_max_jaccard"]):
        return f"{label} max {got['clean_max_jaccard']}!={rec_scale['clean_max_jaccard']}"
    if got["clean_above_threshold"] != rec_scale["clean_above_threshold"]:
        return f"{label} above {got['clean_above_threshold']}"
    if not got["clean_max_below_threshold"]:
        return f"{label} clean max {got['clean_max_jaccard']} not below {M.THRESHOLD}"
    rates = got["plants"]["by_class"]
    if rates["exact_rename"]["firing_rate"] != 1.0:
        return f"{label} rename firing {rates['exact_rename']['firing_rate']}"
    if rates["paraphrase"]["firing_rate"] != 1.0:
        return f"{label} paraphrase firing {rates['paraphrase']['firing_rate']}"
    if rates["full_rewrite"]["firing_rate"] != 0.0:
        return f"{label} rewrite not silent {rates['full_rewrite']['firing_rate']}"
    pr = got["precision_recall"]
    rec_pr = rec_scale["precision_recall"]
    if pr["precision"] != 1.0 or rec_pr["precision"] != 1.0:
        return f"{label} precision {pr['precision']}"
    if pr["recall_in_scope_rename_and_paraphrase"] != 1.0:
        return f"{label} in-scope recall {pr['recall_in_scope_rename_and_paraphrase']}"
    print(
        f"{label} n={got['n']} pairs={got['pair_count']} "
        f"clean_max={got['clean_max_jaccard']:.6f} above={got['clean_above_threshold']} "
        f"rename={rates['exact_rename']['firing_rate']} "
        f"paraphrase={rates['paraphrase']['firing_rate']} "
        f"rewrite={rates['full_rewrite']['firing_rate']} "
        f"precision={pr['precision']} recall_in_scope={pr['recall_in_scope_rename_and_paraphrase']} "
        f"recall_all={pr['recall_including_full_rewrite_as_positive']}"
    )
    return None


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "BLD-0060":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"state {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:BLD-0060" not in blob:
        return fail("sentinel absent")
    if abs(float(doc.get("detector", {}).get("threshold", -1)) - M.THRESHOLD) > EPS:
        return fail("threshold drifted")
    live = M.live_work_units()
    by_n = {int(s["n"]): s for s in doc.get("scale_points") or []}
    if 100 not in by_n or 20480 not in by_n:
        return fail("scale_points missing 100 or 20480")
    for n in (100, 20480):
        err = check_scale(f"n={n}", live, by_n[n])
        if err:
            return fail(err)
    print(
        "silent_class=full_rewrite scope=LEXICAL "
        "rewrite_band=same_as_distinct threshold_not_lowered=true"
    )
    print("SUCCESS:BLD-0060-probe1 planted-mutant precision/recall at n=100 and n=20480")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
