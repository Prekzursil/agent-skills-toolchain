"""IMP-0097 probe2 (mechanically different): self-authored case set is flagged.

Signal 2 (catalog): a package whose benchmark case set it authored alone is flagged
and adds zero, verified against a fixture whose case provenance is KNOWN. Both
states are exercised: the same reproduced record with the self-authorship flag
removed from the provenance DOES score its claimed delta, so the flag is
load-bearing, not decorative.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
MKT = REPO / "tools" / "marketplace"
sys.path.insert(0, str(MKT))

from benchmark_gaming import contribution, is_self_authored, score_with_benchmarks  # noqa: E402
from scenario import load_scenario  # noqa: E402

TARGET = "rec.self-authored.reproduced"


def main() -> int:
    measurements, records, provenance, _raw = load_scenario()
    rec = next(r for r in records if r.record_id == TARGET)
    checks = {}

    checks["fixture_provenance_known"] = (
        isinstance(provenance.get(TARGET), dict)
        and provenance[TARGET].get("self_authored") is True
    )
    checks["is_self_authored_true"] = is_self_authored(rec, provenance) is True

    with_flag = contribution(rec, provenance)
    checks["flagged_contributes_zero"] = with_flag == 0.0

    total_flagged = score_with_benchmarks(measurements, records, provenance).total
    provenance_clean = copy.deepcopy(provenance)
    provenance_clean[TARGET] = {
        k: v for k, v in provenance_clean[TARGET].items() if k != "self_authored"
    }
    without_flag = contribution(rec, provenance_clean)
    total_clean = score_with_benchmarks(measurements, records, provenance_clean).total
    checks["both_states_flag_moves_score"] = (
        without_flag == rec.claimed_delta
        and total_clean == total_flagged + rec.claimed_delta
    )

    out = {
        "unit_id": "IMP-0097",
        "probe": "probe2-self-authored-case-set",
        "flagged_record": TARGET,
        "case_provenance": provenance.get(TARGET),
        "contribution_with_flag": with_flag,
        "contribution_flag_removed": without_flag,
        "total_with_flag": total_flagged,
        "total_flag_removed": total_clean,
        "flag_id": "self-authored-case-set",
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0097-probe2 self-authored reproduced record flagged and scored zero against known case provenance; removing the flag in the mutant provenance lets the same record score its full claimed delta")
        return 0
    print("FAILED:IMP-0097-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
