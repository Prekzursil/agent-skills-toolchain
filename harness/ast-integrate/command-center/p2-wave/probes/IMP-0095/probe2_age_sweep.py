#!/usr/bin/env python3
"""Named probe 2: age-based sweep marks a stored green STALE with hashes unchanged.

The advisory database is an input the registry cannot hash, so age is a second
signal, not a re-implementation of hash comparison. Reviewer obligation: STALE
is never rendered as PASS on record, API, or summary surfaces.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.freshness import (  # noqa: E402
    AGE_STALE,
    STALE,
    VALID,
    age_invalidated,
    age_sweep,
    enumerate_surfaces,
    evaluate_freshness,
    hash_invalidated,
    stamp_verdict,
    summary_view,
)

T0 = 1_700_000_000.0
WINDOW = 3600.0
INPUTS = {
    "sbom_digest": "lockfile-sha-aaaa",
    "component_set": ["leftpad@0.0.1"],
}


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0095-probe2 {msg}")
    return 1


def main() -> int:
    aged = stamp_verdict(
        kind="vulnerability_verdict",
        subject="aged.pkg@1.0.0",
        result="CLEAN",
        inputs=INPUTS,
        computed_at=T0,
        freshness_window_s=WINDOW,
        unhashable_inputs=("advisory_db",),
    )
    fresh = stamp_verdict(
        kind="vulnerability_verdict",
        subject="fresh.pkg@1.0.0",
        result="CLEAN",
        inputs=INPUTS,
        computed_at=T0 + WINDOW - 5,
        freshness_window_s=WINDOW,
        unhashable_inputs=("advisory_db",),
    )
    now = T0 + WINDOW + 1

    if hash_invalidated(aged, INPUTS):
        return fail("hash signal fired with unchanged inputs")
    if not age_invalidated(aged, now):
        return fail("age signal silent past the freshness window")
    if age_invalidated(fresh, now):
        return fail("fresh twin expired (window applied to the wrong record)")

    swept = age_sweep([aged, fresh], now)
    subjects = {row["subject"] for row in swept}
    if subjects != {"aged.pkg@1.0.0"}:
        return fail(f"age_sweep subjects={subjects}")
    if swept[0]["reason"] != AGE_STALE:
        return fail(f"sweep reason {swept[0]['reason']}")

    ev = evaluate_freshness(aged, INPUTS, now)
    if ev["freshness"] != STALE or ev["hash_signal"] != VALID:
        return fail(f"combined evaluation mixed signals: {ev}")
    if ev["age_signal"] != STALE:
        return fail(f"age_signal not STALE: {ev}")

    surfaces = enumerate_surfaces(aged, INPUTS, now)
    if surfaces["surface_result"] != STALE:
        return fail(f"surface_result={surfaces['surface_result']}")
    if surfaces["record"]["result_shown"] == "CLEAN":
        return fail("record view still showed CLEAN")
    if surfaces["api"]["verdict"] in {"CLEAN", "PASS", "GREEN"}:
        return fail(f"API rendered STALE as {surfaces['api']['verdict']}")
    if surfaces["summary"]["pass"] != 0:
        return fail("summary counted STALE as pass")

    summary = summary_view(
        [aged, fresh],
        {"aged.pkg@1.0.0": INPUTS, "fresh.pkg@1.0.0": INPUTS},
        now,
    )
    if summary["pass"] != 1 or summary["stale"] != 1:
        return fail(f"cohort summary {summary['pass']}/{summary['stale']}")
    shown = {row["subject"]: row["result_shown"] for row in summary["rows"]}
    if shown["aged.pkg@1.0.0"] != STALE:
        return fail("aged record shown as pass in cohort summary")
    if shown["fresh.pkg@1.0.0"] != "CLEAN":
        return fail("fresh twin was not still CLEAN")

    payload = {
        "probe": "probe2-age-sweep",
        "unit_id": "IMP-0095",
        "unchanged_hashes": True,
        "age_signal": ev["age_signal"],
        "hash_signal": ev["hash_signal"],
        "swept": [row["subject"] for row in swept],
        "aged_shown": surfaces["record"]["result_shown"],
        "api_verdict": surfaces["api"]["verdict"],
        "summary_pass": summary["pass"],
        "summary_stale": summary["stale"],
        "stale_never_pass": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "age_stale=True hash_valid=True stale_never_pass=True "
        f"swept={payload['swept']}"
    )
    print("SUCCESS:IMP-0095-probe2 age sweep and STALE-never-PASS reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
