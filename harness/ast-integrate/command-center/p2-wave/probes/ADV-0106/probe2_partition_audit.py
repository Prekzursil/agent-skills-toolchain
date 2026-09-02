#!/usr/bin/env python3
"""Probe 2: partition-content audit on the live council partition runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{E.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    meas = E.measure()
    if not meas["honest_canary_silent"]:
        return fail("honest withheld canary leaked to partitioned seat")
    if not meas["honest_fact_leak"]:
        return fail(
            "honest paraphrase did not carry withheld facts; probe 2 has no live finding"
        )
    if not meas["naive_canary_all_fire"]:
        return fail("a naive carrier did not leak the withheld canary")
    if not meas["detector_control_fires"]:
        return fail("detector control (canary planted in allowed) was silent")
    if not meas["assembly_leak_fires"]:
        return fail("assembly-leak control was silent")
    if not meas["allowed_canary_visible_honest"]:
        return fail("allowed canary not visible to partitioned seat")
    if not meas["empty_search_rejected"]:
        return fail("empty search was accepted as a clean withhold")
    if not meas["redacted_paraphrase_twin_silent"]:
        return fail("fully redacted paraphrase twin still showed withheld facts")
    if meas["partition_verdict"] != "CONFIRMED":
        return fail(f"partition_verdict={meas['partition_verdict']}")
    if not meas["oracle_can_go_red"]:
        return fail("negative-control oracle cannot go red")

    art = E.REPO / E.OUT_REL
    if art.is_file():
        text = art.read_text(encoding="utf-8")
        doc = json.loads(text)
        if E.SENTINEL not in text:
            return fail("catalog sentinel absent")
        rec = (doc.get("measurements") or {}).get("honest_fact_leak")
        if rec is not True:
            return fail("artifact honest_fact_leak is not true")

    payload = {
        "probe": "probe2-partition-audit",
        "unit_id": E.UNIT,
        "pass": True,
        "catalog_probe": E.CATALOG_PROBE2,
        "honest_canary_silent": True,
        "honest_fact_leak": True,
        "honest_fact_paths": meas["honest_fact_paths"],
        "naive_canary_all_fire": True,
        "detector_control_fires": True,
        "assembly_leak_fires": True,
        "empty_search_rejected": True,
        "redacted_twin_silent": True,
        "verdict": meas["partition_verdict"],
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    print(
        "honest_canary_silent=True honest_fact_leak=True "
        f"naive_all_fire={meas['naive_canary_all_fire']} "
        f"facts={meas['honest_fact_paths']}"
    )
    print(
        "SUCCESS:ADV-0106-probe2 partition-content audit: canary withheld, "
        "withheld facts still present in honest paraphrase; naive carriers red"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
