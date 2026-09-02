#!/usr/bin/env python3
"""Probe 2: each captured seed is load-bearing; decorative seeds FIRE.

Oracle: transcript diff (first differing event) plus an independent recount
of actor sequence / tool-result order / timestamps from the event list.

Negative control (verbatim): perturbing sampling on the real engine MUST
change the transcript; the same perturbation on DecorativeSamplingCouncil
MUST NOT change it, so the check fires on the planted-bad mutant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import replay_engine as E  # noqa: E402

AXES = ("sampling", "tool_order", "clock", "recruitment")


def main() -> int:
    rows = [E.perturb_axis(axis) for axis in AXES]
    mutant = E.mutant_sampling_is_decorative()
    base = E.run_from_seeds()
    recount = E.independent_recount(base.transcript)
    expected_kinds = {"recruit", "utter", "tool_call", "tool_result", "stop"}
    print(json.dumps({"perturbations": rows, "mutant": mutant, "recount": recount}, sort_keys=True))
    for row in rows:
        print(
            f"perturb axis={row['axis']} changed={row['changed']} "
            f"base={row['base_seed']} pert={row['perturbed_seed']} "
            f"sha_base={row['sha_base'][:16]} sha_pert={row['sha_perturbed'][:16]} "
            f"first_diff_index={row['first_diff_index']} "
            f"kind_base={row['first_diff_kind_base']} kind_pert={row['first_diff_kind_perturbed']}"
        )
        if not row["changed"]:
            print(f"FAILED:CNL-0011-probe2 seed {row['axis']} is decorative")
            return 1
        if row["first_diff_index"] is None:
            print(f"FAILED:CNL-0011-probe2 seed {row['axis']} changed hash but no event diff")
            return 1
    print(
        "NEGATIVE CONTROL (verbatim): perturb sampling seed +1 on the real engine; "
        "the check requires sha_base != sha_perturbed. "
        f"Observed real_changes={mutant['real_changes']} "
        f"sha_base={mutant['real_sha_base']} sha_perturbed={mutant['real_sha_perturbed']}."
    )
    print(
        "NEGATIVE CONTROL (planted-bad mutant DecorativeSamplingCouncil): "
        "the same sampling perturbation must leave the transcript UNCHANGED, "
        "proving the check fires when a seed is serialised but unused. "
        f"Observed mutant_changes={mutant['mutant_changes']} "
        f"check_fires_on_mutant={mutant['check_fires_on_mutant']} "
        f"mutant_sha_base={mutant['mutant_sha_base']} "
        f"mutant_sha_perturbed={mutant['mutant_sha_perturbed']}."
    )
    if not mutant["check_silent_on_real"]:
        print("FAILED:CNL-0011-probe2 sampling perturbation silent on real engine")
        return 1
    if not mutant["check_fires_on_mutant"]:
        print("FAILED:CNL-0011-probe2 decorative-sampling mutant was not detected")
        return 1
    print(
        f"recount events={recount['event_count']} kinds={recount['kinds']} "
        f"roster={recount['roster']} ticks_ok={recount['ticks_strictly_increasing']}"
    )
    if recount["event_count"] != len(base.transcript):
        print("FAILED:CNL-0011-probe2 independent recount disagreed on event_count")
        return 1
    if set(recount["kinds"]) != expected_kinds:
        print(f"FAILED:CNL-0011-probe2 unexpected kinds {recount['kinds']}")
        return 1
    if not recount["ticks_strictly_increasing"]:
        print("FAILED:CNL-0011-probe2 timestamps not strictly increasing")
        return 1
    if not recount["roster"] or len(recount["roster"]) != 3:
        print("FAILED:CNL-0011-probe2 roster recount failed")
        return 1
    if len(recount["tool_result_sequence"]) != 6:
        print("FAILED:CNL-0011-probe2 expected 6 tool_result events (2 rounds x 3 speakers)")
        return 1
    print("SUCCESS:CNL-0011-probe2 all four seeds load-bearing; decorative mutant fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
