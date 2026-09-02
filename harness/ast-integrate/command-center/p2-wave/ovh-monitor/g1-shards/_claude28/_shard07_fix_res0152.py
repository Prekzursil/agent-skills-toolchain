#!/usr/bin/env python3
"""RES-0152: merge live-recomputed domain fields back into the envelope.

The envelope rewrite destroyed definition/calibration/two_pass and the lock
flag; the shared measurement-run schema is now a generic envelope, so the
unit emitter cannot be re-run wholesale. This recomputes measure() live
(engine.py, local disk only) and merges exactly the blocks the probes
assert, leaving all envelope fields intact.
"""
import sys
from pathlib import Path

SHARD_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SHARD_DIR))
import _shard07_lib as L

UNIT = L.REPO / "command-center/p2-wave/probes/RES-0152"
sys.path.insert(0, str(UNIT))
from engine import measure  # noqa: E402

ART = (
    "command-center/research/evidence-quality/"
    "RES-0152-confidence-band-calibration-set.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0152/probe1_unknown_exclusion.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0152/probe2_two_pass.py"
)


def compact_row(row: dict) -> dict:
    keep = (
        "id", "unit_id", "claim", "source_path", "source_kind", "band",
        "band_raw", "band_map_reason", "register", "outcome", "outcome_why",
        "outcome_source", "outcome_kind", "scored", "lane", "control",
    )
    return {k: row[k] for k in keep if k in row}


measured = measure()
assert measured["min_scored_met"], f"scored_forward={measured['n_scored_forward']} < 60"
assert measured["detector_control"]["pass"], "detector_control failed live"
tp = measured["two_pass"]
assert tp["within_10_percent"], "two-pass delta exceeds 10%"
assert (tp.get("catalog_path_corroboration") or {}).get("pass"), "corroboration failed"

doc = L.load(ART)

doc["definition"] = {
    "id": measured["definition_id"],
    "path": "command-center/p2-wave/probes/RES-0152/DEFINITION.json",
    "sha256": measured["definition_sha256"],
    "frozen_before_count": True,
    "same_rule_all_vendors": True,
}
doc["definition_locked_hash_before_enumerate"] = measured[
    "definition_locked_hash_before_enumerate"
]
doc["window"] = {
    "start": measured["window"]["start"],
    "end": measured["window"]["end"],
    "days": int(measured["window"]["days"]),
}
doc["two_pass"] = {
    "vendor_id": tp["vendor_id"],
    "pass_a": tp["pass_a"],
    "pass_b": tp["pass_b"],
    "pass_a_count": tp["pass_a_count"],
    "pass_b_count": tp["pass_b_count"],
    "relative_delta": tp["relative_delta"],
    "within_10_percent": tp["within_10_percent"],
    "frozen_n": tp.get("frozen_n"),
    "catalog_path_corroboration": {
        "n": (tp.get("catalog_path_corroboration") or {}).get("n"),
        "present": (tp.get("catalog_path_corroboration") or {}).get("present"),
        "pass": (tp.get("catalog_path_corroboration") or {}).get("pass"),
    },
}
likely = measured["likely"]
doc["calibration"] = {
    "n_rows": measured["n_rows"],
    "n_scored": measured["n_scored"],
    "n_scored_forward": measured["n_scored_forward"],
    "n_held_forward": measured["n_held_forward"],
    "n_missed_forward": measured["n_missed_forward"],
    "n_unknown_excluded": measured["n_unknown_excluded"],
    "min_scored_met": measured["min_scored_met"],
    "band_table": measured["band_table"],
    "likely": likely,
    "over_under_likely": measured["over_under_likely"],
    "brier": measured["brier"],
    "bias_direction": measured["bias_direction"],
    "bias_magnitude": measured["bias_magnitude"],
    "residue_unmapped_n": measured["residue_unmapped_n"],
    "residue_sample": measured["residue_sample"],
    "unknown_control_ids": measured["unknown_control_ids"],
    "inputs_status": measured["inputs_status"],
    "scored_forward_claims": [
        compact_row(r)
        for r in measured["rows"]
        if r.get("scored") is True and r.get("register") == "forward-looking"
    ],
    "unknown_control_claims": [
        compact_row(r)
        for r in measured["rows"]
        if r.get("control") == "unknown-must-exclude"
    ],
    "banded_claim_census": [
        compact_row(r)
        for r in measured["rows"]
        if r.get("source_kind") == "banded-json-claim"
    ],
}
doc["maintenance_implication"] = measured["maintenance_implication"]
doc.setdefault("report_kind", "measurement-run")
doc.setdefault("named_probes", [{"id": "probe1", "command": P1}, {"id": "probe2", "command": P2}])

print(
    f"live: scored_forward={measured['n_scored_forward']} "
    f"held={measured['n_held_forward']} unknown_excluded={measured['n_unknown_excluded']} "
    f"pass_a={tp['pass_a_count']} pass_b={tp['pass_b_count']} "
    f"likely n={likely['n']} status={likely['status']} "
    f"def_sha={measured['definition_sha256'][:12]}"
)

L.save(ART, doc)
L.refresh_manifest("RES-0152", [ART])
print("RES-0152 domain fields merged back from live measure()")
