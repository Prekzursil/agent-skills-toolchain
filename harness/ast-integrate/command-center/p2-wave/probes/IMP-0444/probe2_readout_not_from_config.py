#!/usr/bin/env python3
"""IMP-0444 probe 2: readout is measured; raising a ceiling is visible; mutant fires."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from concurrency_governor import (  # noqa: E402
    DEFAULT_CEILINGS,
    LiveReadout,
    SUBSTRATES,
    audit_readout_independence,
    load_ceilings,
    run_schedule,
    snapshot_uses_len,
    synthetic_catalog_2048,
)

UNIT = "IMP-0444"
ART = REPO / "command-center" / "receipts" / "IMP-0444.json"
CFG = REPO / "command-center" / "config" / "substrate-ceilings.json"
GOV = REPO / "tools" / "command-center" / "concurrency_governor.py"
MUTANT = HERE / "fixtures" / "derived_readout_mutant.py"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = "SENTINEL:IMP-0444:CONCURRENCY-CEILING-HELD"
FINDING = "readout-derived-from-config"


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
    src = GOV.read_text(encoding="utf-8")
    mutant_src = MUTANT.read_text(encoding="utf-8")
    honest = audit_readout_independence(src, label=str(GOV.relative_to(REPO)))
    planted = audit_readout_independence(
        mutant_src, label=str(MUTANT.relative_to(REPO))
    )
    planted_ids = {f["id"] for f in planted}
    honest_silent = honest == []
    mutant_fires = FINDING in planted_ids
    uses_len = snapshot_uses_len(src)

    ceilings = load_ceilings(CFG)
    units = synthetic_catalog_2048(duration_ticks=4, ready_at=0)
    base = run_schedule(units, ceilings=ceilings, sample_hz=1)
    base_peaks = base.peaks()

    raised = dict(ceilings)
    raised["local-parallel"] = ceilings["local-parallel"] + 4
    after = run_schedule(units, ceilings=raised, sample_hz=1)
    after_peaks = after.peaks()
    raise_visible = (
        after_peaks["local-parallel"] > base_peaks["local-parallel"]
        and after_peaks["local-parallel"] == raised["local-parallel"]
        and base_peaks["local-parallel"] == ceilings["local-parallel"]
    )

    stored = dict(base.readout.peaks())
    base.ceilings["local-parallel"] = 9999
    posthoc_unchanged = base.readout.peaks() == stored

    zero = LiveReadout()
    zero.record(0, {s: 0 for s in SUBSTRATES}, {s: 0 for s in SUBSTRATES})
    zero_peaks = zero.peaks()
    zero_is_zero = all(v == 0 for v in zero_peaks.values()) and zero_peaks != ceilings

    sys.path.insert(0, str(HERE / "fixtures"))
    import derived_readout_mutant as mutant  # noqa: E402

    derived = mutant.LiveReadout(ceilings)
    derived_peaks = derived.peaks()
    derived_copies_config = (
        derived_peaks == ceilings
        and derived.peak("local-serialized") == ceilings["local-serialized"]
    )

    receipt = check_receipt()
    both = {
        "good_silent": honest_silent,
        "bad_fires": mutant_fires,
        "raise_visible": raise_visible,
        "posthoc_config_does_not_rewrite_readout": posthoc_unchanged,
        "zero_samples_not_ceiling": zero_is_zero,
        "mutant_copies_ceiling": derived_copies_config,
    }
    passed = (
        honest_silent
        and mutant_fires
        and uses_len
        and raise_visible
        and posthoc_unchanged
        and zero_is_zero
        and derived_copies_config
        and receipt["ok"]
        and ceilings == DEFAULT_CEILINGS
    )
    report = {
        "probe": "probe2-readout-not-from-config",
        "unit_id": UNIT,
        "honest_findings": honest,
        "planted_findings": planted,
        "planted_ids": sorted(planted_ids),
        "snapshot_uses_len": uses_len,
        "base_peaks": base_peaks,
        "raised_peaks": after_peaks,
        "raised_ceiling_local_parallel": raised["local-parallel"],
        "zero_peaks": zero_peaks,
        "derived_peaks": derived_peaks,
        "both_states": both,
        "receipt": receipt,
        "pass": passed,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        print("FAILED:IMP-0444-probe2 readout derived-from-config control")
        return 1
    print("SUCCESS:IMP-0444-probe2 readout is measured; ceiling raise is visible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
