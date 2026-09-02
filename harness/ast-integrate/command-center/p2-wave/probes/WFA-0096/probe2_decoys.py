#!/usr/bin/env python3
"""Probe 2: independent decoy silence + both-states red-capability.

Uses exclusive-item cardinality (not Jaccard) as the second signal. A
detector that fires on everything has perfect recall and zero value; this
probe requires the three genuine decoys to stay silent, and proves the
check can go red by showing threshold=0 would flag those same decoys.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import control as C  # noqa: E402
import differ as D  # noqa: E402

OUT = HERE / "probe2-decoys.raw.json"
ART = REPO / "command-center/wfa/WFA-0096-differ-mutant-control.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0096-probe2 {msg}")
    return 1


def check_artifact(live: dict) -> str:
    if not ART.is_file():
        return "absent-skip"
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:WFA-0096" not in text:
        return "sentinel-absent"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared:{doc.get('state')}"
    if float(doc.get("threshold")) != float(live["threshold"]):
        return "artifact-threshold-stale-rerun-required"
    if str(doc.get("differ_sha256") or "") != live["differ_sha256"]:
        return "artifact-differ-stale-rerun-required"
    art_decoys = {row["plant_id"]: row for row in doc.get("decoys") or [] if isinstance(row, dict)}
    if len(art_decoys) != 3:
        return f"artifact-decoy-count:{len(art_decoys)}"
    for row in live["decoys"]:
        art = art_decoys.get(row["plant_id"])
        if not art:
            return f"artifact-missing-decoy:{row['plant_id']}"
        if art.get("silent") is not True:
            return f"artifact-decoy-not-silent:{row['plant_id']}"
        if abs(float(art.get("nearest_score")) - float(row["nearest_score"])) > 1e-9:
            return "artifact-decoy-score-mismatch"
    if doc.get("decoys_silent") is not True:
        return "artifact-decoys_silent-false"
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("executed_both_states_control") is not True:
        return "artifact-reviewer-did-not-rerun-both-states"
    return "ok"


def main() -> int:
    live = C.run_control()
    if live["threshold"] != D.THRESHOLD:
        return fail("threshold drifted from differ.py")
    if not live["always_fire_would_flag_decoys"]:
        return fail("threshold=0 negative control did not flag decoys (vacuous silence)")
    if live["toy_fixture"]:
        return fail("decoys were scored on a toy fixture")

    for row in live["decoys"]:
        exclusive = row["exclusive_vs_nearest"]
        print(
            f"decoy plant={row['plant_id']} source={row['host_id']} "
            f"nearest={row['nearest_id']} score={row['nearest_score']} "
            f"detected={row['detected']} exclusive_vs_nearest={exclusive} "
            f"independent_dup={row['independent_duplicate_vs_nearest']}"
        )
        if row["detected"]:
            return fail(
                f"decoy {row['plant_id']} fired nearest={row['nearest_id']} "
                f"score={row['nearest_score']}"
            )
        if row["independent_duplicate_vs_nearest"] is not False:
            return fail("independent exclusive-count called decoy a duplicate of nearest")
        if exclusive is None or exclusive <= D.INDEPENDENT_EXCLUSIVE_MAX:
            return fail(f"decoy exclusive-vs-nearest too small: {exclusive}")
        if row["nearest_score"] >= D.THRESHOLD:
            return fail("nearest score at-or-above threshold despite detected=false")
    if not live["decoys_silent"]:
        return fail("decoys_silent flag false")
    if not live["mutants_caught"]:
        return fail("reviewer both-states: mutants were not caught")

    art_status = check_artifact(live)
    if art_status not in {"ok", "absent-skip"}:
        return fail(art_status)

    payload = {
        "pass": True,
        "independent_reviewer": True,
        "executed_both_states_control": True,
        "method": "exclusive-item-cardinality-not-jaccard",
        "decoys_silent": True,
        "mutants_caught": True,
        "always_fire_would_flag_decoys": True,
        "never_fire_would_miss_mutants": live["never_fire_would_miss_mutants"],
        "threshold": live["threshold"],
        "differ_sha256": live["differ_sha256"],
        "decoys": live["decoys"],
        "artifact_check": art_status,
        "reviewer_id": "WFA-0096-probe2-exclusive-cardinality-decoy-silence",
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"silent={len(live['decoys'])} always_fire_red={live['always_fire_would_flag_decoys']} "
        f"artifact={art_status} threshold={live['threshold']}"
    )
    print("SUCCESS:WFA-0096-probe2 decoys silent on independent exclusive-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
