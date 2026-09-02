#!/usr/bin/env python3
"""Probe 2: apply the strongest locally runnable detector (unique canary).

Both-states: planted oracle must fire; clean boilerplate must stay silent.
Live prompt-surface scan extra hits must be 0. Artifact applied_result must
match the live recomputation (second signal: file bytes, not the JSON copy).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import ngram_canary as C  # noqa: E402
import table as T  # noqa: E402

ART = REPO / "command-center/research/RES-0089.json"


def main() -> int:
    live = C.apply_to_program_benchmark()
    states = live["both_states"]
    scan = live["live_prompt_scan"]
    print(
        "planted_hit={0} clean_hit={1} extra={2} verdict={3}".format(
            states["planted_exact_hit"],
            states["clean_exact_hit"],
            scan["extra_hit_count"],
            live["verdict"],
        )
    )
    print(
        "byte_signal planted={0} clean={1}".format(
            states["second_signal_canary_in_planted_bytes"],
            states["second_signal_canary_in_clean_bytes"],
        )
    )
    if live["verdict"] != "APPLIED-PASS":
        print("FAILED:RES-0089-probe2 applied detector did not pass both-states")
        return 1
    if not ART.is_file():
        print("FAILED:RES-0089-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    recorded = doc.get("applied_result") or {}
    keys = (
        "verdict",
        "benchmark_id",
        "detector_applied",
    )
    for k in keys:
        if recorded.get(k) != live.get(k):
            print(f"FAILED:RES-0089-probe2 applied_result.{k} drift")
            return 1
    rec_states = recorded.get("both_states") or {}
    for k in (
        "planted_exact_hit",
        "clean_exact_hit",
        "measured_fpr_on_clean_control",
        "measured_tpr_on_planted_control",
        "second_signal_canary_in_planted_bytes",
        "second_signal_canary_in_clean_bytes",
    ):
        if rec_states.get(k) != states.get(k):
            print(f"FAILED:RES-0089-probe2 both_states.{k} drift")
            return 1
    if (recorded.get("live_prompt_scan") or {}).get("extra_hit_count") != scan[
        "extra_hit_count"
    ]:
        print("FAILED:RES-0089-probe2 extra_hit_count drift")
        return 1

    table = doc.get("detector_table") or []
    local = next((r for r in table if r.get("id") == "local-canary-g1"), None)
    if local is None:
        print("FAILED:RES-0089-probe2 local-canary-g1 row missing")
        return 1
    if local.get("false_positive_rate") != "0.0":
        print("FAILED:RES-0089-probe2 local FPR not the measured 0.0")
        return 1
    if not local.get("may_disqualify_a_result"):
        print("FAILED:RES-0089-probe2 measured-FPR detector cannot disqualify")
        return 1
    oren = next((r for r in table if r.get("id") == "oren-permutation-exchangeability"), None)
    if not oren or not oren.get("may_disqualify_a_result"):
        print("FAILED:RES-0089-probe2 Oren must remain a disqualifier in the table")
        return 1
    if T.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:RES-0089-probe2 sentinel missing from artifact")
        return 1
    print("applied_result matches live recompute")
    print("SUCCESS:RES-0089-probe2 applied canary both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
