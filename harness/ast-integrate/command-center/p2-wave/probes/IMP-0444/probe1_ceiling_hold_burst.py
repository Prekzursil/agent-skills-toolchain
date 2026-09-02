#!/usr/bin/env python3
"""IMP-0444 probe 1: ceiling holds under a 2048-unit burst; ungated exceeds."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from concurrency_governor import (  # noqa: E402
    DEFAULT_CEILINGS,
    SUBSTRATES,
    load_ceilings,
    run_schedule,
    substrate_counts,
    synthetic_catalog_2048,
)

UNIT = "IMP-0444"
ART = REPO / "command-center" / "receipts" / "IMP-0444.json"
CFG = REPO / "command-center" / "config" / "substrate-ceilings.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SENTINEL:IMP-0444:CONCURRENCY-CEILING-HELD"


def check_receipt() -> dict:
    if not ART.is_file():
        return {"present": False, "ok": True, "skipped": True}
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    ok = st not in NOT_DELIVERING and SENTINEL in text
    return {
        "present": True,
        "ok": ok,
        "state": st,
        "sentinel_present": SENTINEL in text,
        "skipped": False,
    }


def main() -> int:
    ceilings = load_ceilings(CFG)
    units = synthetic_catalog_2048(duration_ticks=4, ready_at=0)
    counts = substrate_counts(units)
    gated = run_schedule(units, ceilings=ceilings, sample_hz=1)
    peaks = gated.peaks()

    ungated = run_schedule(
        units, ceilings={s: 10**6 for s in SUBSTRATES}, sample_hz=1
    )
    ungated_peaks = ungated.peaks()

    stagger_cfg = {s: 0 for s in SUBSTRATES}
    stagger_cfg["cloud-batch"] = 2
    staggered = run_schedule(
        units, ceilings=ceilings, stagger_ticks=stagger_cfg, sample_hz=1
    )
    cloud_launches = [
        ln.tick for ln in staggered.launches if ln.substrate == "cloud-batch"
    ]
    cloud_gaps = [b - a for a, b in zip(cloud_launches, cloud_launches[1:])]

    held = all(peaks.get(s, 0) <= ceilings[s] for s in SUBSTRATES)
    saturated = all(
        peaks.get(s, 0) == min(ceilings[s], counts[s]) for s in SUBSTRATES
    )
    ungated_exceeds = all(
        ungated_peaks.get(s, 0) == counts[s] and counts[s] > ceilings[s]
        for s in SUBSTRATES
    )
    logical_not_simultaneous = gated.n_units == 2048 and sum(peaks.values()) < 2048
    all_ran = len(gated.launches) == 2048 and len(gated.completions) == 2048
    sampled = gated.readout.n_samples() >= 2 and gated.sample_hz == 1
    stagger_held = bool(cloud_gaps) and min(cloud_gaps) >= 2
    serialized_is_one = peaks.get("local-serialized") == 1
    receipt = check_receipt()

    report = {
        "probe": "probe1-ceiling-hold-burst",
        "unit_id": UNIT,
        "n_units": gated.n_units,
        "counts": counts,
        "ceilings": ceilings,
        "peaks_gated": peaks,
        "peaks_ungated": ungated_peaks,
        "held": held,
        "saturated": saturated,
        "ungated_exceeds": ungated_exceeds,
        "logical_not_simultaneous": logical_not_simultaneous,
        "all_ran": all_ran,
        "sampled_1hz": sampled,
        "n_samples": gated.readout.n_samples(),
        "makespan_ticks": gated.makespan_ticks,
        "stagger_min_gap_cloud_batch": min(cloud_gaps) if cloud_gaps else None,
        "stagger_held": stagger_held,
        "serialized_is_one": serialized_is_one,
        "both_states": {
            "gated_held": held,
            "ungated_exceeds": ungated_exceeds,
        },
        "receipt": receipt,
        "config_path": str(CFG.relative_to(REPO)),
        "defaults_match_file": ceilings == DEFAULT_CEILINGS,
        "pass": False,
    }
    passed = (
        held
        and saturated
        and ungated_exceeds
        and logical_not_simultaneous
        and all_ran
        and sampled
        and stagger_held
        and serialized_is_one
        and receipt["ok"]
        and report["defaults_match_file"]
    )
    report["pass"] = passed
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        print("FAILED:IMP-0444-probe1 ceiling-hold burst")
        return 1
    print("SUCCESS:IMP-0444-probe1 ceiling held under 2048-unit burst")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
