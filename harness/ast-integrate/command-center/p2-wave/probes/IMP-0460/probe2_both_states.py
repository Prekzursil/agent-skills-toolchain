#!/usr/bin/env python3
"""Probe 2: both-states — malformed config must lower the observed marker count.

The independent reviewer for the broken-state reading. A $schema key (Codex
precedent) must load fewer hooks than the repaired config; repair must restore
the count. Config listing and an inert declared-count stub stay silent in both
states and are therefore not this probe.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from hook_load.load_probe import both_states  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0460.json"
SENTINEL = "SENTINEL:IMP-0460:HOOKS-LOAD-VERIFIED"


def main() -> int:
    report = both_states()
    good = report["good"]["compare"]
    bad = report["malformed"]["compare"]
    restored = report["restored"]["compare"]
    listing = report["listing"]
    inert = report["inert_stub"]

    print(json.dumps({
        "declared_count": report["declared_count"],
        "good_observed": good["observed_count"],
        "malformed_observed": bad["observed_count"],
        "restored_observed": restored["observed_count"],
        "malformed_missing": bad["missing_markers"],
        "malformed_unknown_fields": report["malformed"]["load"]["unknown_fields"],
        "listing_same": listing["same_in_both_states"],
        "inert_silent": inert["silent_in_both_states"],
        "probe_sees_broken_state": report["probe_sees_broken_state"],
        "repaired_restores": report["repaired_restores"],
        "pass": report["pass"],
    }, sort_keys=True))

    if not good["equal"]:
        print("FAILED:IMP-0460-probe2 repaired state is not equal")
        return 1
    if not report["probe_sees_broken_state"]:
        print(
            "FAILED:IMP-0460-probe2 malformed observed "
            f"{bad['observed_count']} was not lower than good "
            f"{good['observed_count']} (silent in both states)"
        )
        return 1
    if bad["observed_count"] >= good["observed_count"]:
        print("FAILED:IMP-0460-probe2 malformed count not strictly lower")
        return 1
    if bad["missing_markers"] != report["declared_ids"]:
        print(
            "FAILED:IMP-0460-probe2 missing markers not fully named "
            f"{bad['missing_markers']}"
        )
        return 1
    if not report["repaired_restores"] or not restored["equal"]:
        print("FAILED:IMP-0460-probe2 repaired config did not restore count")
        return 1
    if not listing["same_in_both_states"]:
        print("FAILED:IMP-0460-probe2 listing control did not stay constant")
        return 1
    if listing["accepted_as_load_evidence"] is not False:
        print("FAILED:IMP-0460-probe2 listing must not be load evidence")
        return 1
    if listing["good_files"] != listing["bad_files"]:
        print("FAILED:IMP-0460-probe2 listing files drifted across states")
        return 1
    if not inert["silent_in_both_states"] or not inert["measures_nothing"]:
        print("FAILED:IMP-0460-probe2 inert stub must be silent in both states")
        return 1
    if inert["good_count"] != inert["bad_count"]:
        print("FAILED:IMP-0460-probe2 inert stub discriminated (it must not)")
        return 1
    if "$schema" not in report["malformed"]["load"]["unknown_fields"]:
        print("FAILED:IMP-0460-probe2 $schema was not the refusal field")
        return 1
    if not report["pass"]:
        print("FAILED:IMP-0460-probe2 both_states pass=false")
        return 1

    if not ART.is_file():
        print("FAILED:IMP-0460-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0460-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0460-probe2 self-declared {doc.get('state')}")
        return 1
    both = doc.get("both_states") or {}
    if both.get("malformed_observed_count") != bad["observed_count"]:
        print("FAILED:IMP-0460-probe2 receipt malformed_observed_count drifted")
        return 1
    if both.get("good_observed_count") != good["observed_count"]:
        print("FAILED:IMP-0460-probe2 receipt good_observed_count drifted")
        return 1
    if both.get("probe_sees_broken_state") is not True:
        print("FAILED:IMP-0460-probe2 receipt missing broken-state reading")
        return 1
    if both.get("listing_silent_in_both_states") is not True:
        print("FAILED:IMP-0460-probe2 receipt listing_silent drifted")
        return 1

    print(
        f"good={good['observed_count']} malformed={bad['observed_count']} "
        f"restored={restored['observed_count']} "
        f"listing_silent={listing['same_in_both_states']} "
        f"inert_silent={inert['silent_in_both_states']}"
    )
    print("SUCCESS:IMP-0460-probe2 both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
