"""Both-states matrix, detector-control-first, numeric false-positive rate."""
from __future__ import annotations

import json
from typing import Any

from detector import detect, distinguisher
from fixtures import (
    CLEAN,
    CONTROL_ID,
    PAIR_EXHAUSTED,
    PAIR_GENUINE,
    PLANTED,
    load,
)


def artifact_payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live in report/extensions under receipt_core additionalProperties=false."""
    merged: dict[str, Any] = dict(doc)
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        merged.update(ext)
    report = doc.get("report")
    if isinstance(report, dict):
        merged.update(report)
    return merged


def run_matrix() -> dict[str, Any]:
    control_run = load(CONTROL_ID)
    control = detect(control_run)
    # Detector-control: known-present MUST fire before any absence is claimed.
    if not control["fired"]:
        return {
            "ok": False,
            "reason": "detector-control-missed-known-present",
            "control": control,
        }

    planted = {rid: detect(load(rid)) for rid in PLANTED}
    clean = {rid: detect(load(rid)) for rid in CLEAN}
    planted_fired = all(row["fired"] for row in planted.values())
    clean_silent = not any(row["fired"] for row in clean.values())
    fired_on_clean = sum(1 for row in clean.values() if row["fired"])
    clean_count = len(clean)
    rate = fired_on_clean / clean_count

    d_gen = distinguisher(load(PAIR_GENUINE))
    d_exh = distinguisher(load(PAIR_EXHAUSTED))
    pair_distinct = d_gen != d_exh

    nc_src = load(PAIR_EXHAUSTED)
    mutant = json.loads(json.dumps(nc_src))
    mutant["id"] = "negative-control-kind-rewrite"
    mutant["outcome"]["kind"] = "no-decision"
    mutant["outcome"]["termination_cause"] = "deliberative"
    nc = detect(mutant)

    ok = (
        planted_fired
        and clean_silent
        and pair_distinct
        and nc["fired"]
        and rate == 0.0
    )
    return {
        "ok": ok,
        "detector_control": {
            "known_present_id": CONTROL_ID,
            "fired": control["fired"],
            "fired_before_absence_claimed": True,
            "codes": control["codes"],
        },
        "planted": {rid: {"fired": row["fired"], "codes": row["codes"]} for rid, row in planted.items()},
        "clean": {rid: {"fired": row["fired"], "codes": row["codes"]} for rid, row in clean.items()},
        "planted_bad_fired": planted_fired,
        "known_good_silent": clean_silent,
        "false_positive_rate": {
            "fired_on_clean": fired_on_clean,
            "clean_count": clean_count,
            "rate": rate,
            "formula": "fired_on_clean / clean_count",
        },
        "distinguisher_pair": {
            "genuine_no_decision": list(d_gen),
            "cap_exhausted": list(d_exh),
            "distinct": pair_distinct,
            "mechanism": "tuple(kind, termination_cause, cap_remaining) — not detect().fired",
        },
        "negative_control": {
            "id": "NC-REWRITE-EXHAUSTED-AS-NO-DECISION",
            "rejects": "good-cap-exhausted with kind rewritten to no-decision",
            "fired": nc["fired"],
            "codes": nc["codes"],
            "verbatim": (
                f"rewrite kind=no-decision termination_cause=deliberative on "
                f"{PAIR_EXHAUSTED}; detect.fired={nc['fired']} codes={nc['codes']}"
            ),
        },
    }
