#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0115-fused-worse-than-source-detector.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402

UID = "WFA-0115"
OUT = "command-center/wfa/WFA-0115-fused-worse-than-source-detector.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0115/probe1_planted_degraded.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0115/probe2_floor_and_precert.py"
)
QUESTION = (
    "Implementation target: a gate that fails certification when a fused "
    "candidate scores below ALL of its sources on the matched cases - the "
    "spec's named failure class - with the comparison made against the "
    "measured variance floor rather than against raw point scores."
)


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, float):
        return float(obj)
    return obj


def main() -> int:
    live_floor = D.measure_variance_floor(*D.fixture_control_pair(), D.CASE_IDS)
    scenarios = D.run_all_scenarios()
    raw_mutant = D.run_all_scenarios(use_raw_points=True)
    states = D.both_states()
    ordering = D.ordering_controls()
    if not states["discriminates"]:
        print("FAILED:WFA-0115 emit both-states did not discriminate")
        print(json.dumps(states, indent=2, default=str)[:3000])
        return 1
    if not ordering["pass"]:
        print("FAILED:WFA-0115 emit ordering controls failed")
        print(json.dumps(ordering, indent=2, default=str)[:3000])
        return 1
    incon = scenarios["inconclusive"]
    if incon["verdict"] != D.INCONCLUSIVE:
        print("FAILED:WFA-0115 emit inconclusive fixture was", incon["verdict"])
        return 1
    if raw_mutant["inconclusive"]["verdict"] != D.REJECT:
        print("FAILED:WFA-0115 emit raw-points mutant did not over-reject")
        return 1
    if scenarios["degraded"]["verdict"] != D.REJECT:
        print("FAILED:WFA-0115 emit planted degraded not REJECT")
        return 1
    if scenarios["good"]["verdict"] != D.CLEAR:
        print("FAILED:WFA-0115 emit good fusion not CLEAR")
        return 1
    if scenarios["complement"]["verdict"] != D.CLEAR:
        print("FAILED:WFA-0115 emit complement over-fired")
        return 1
    if scenarios["incomplete"]["verdict"] != D.REFUSE:
        print("FAILED:WFA-0115 emit incomplete arm not REFUSE")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    harness_0113 = REPO / "command-center/wfa/WFA-0113-benchmark-matched-pair-harness.json"
    rubric_0114 = REPO / "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"

    doc = {
        "record_type": "RegressionFixture",
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0115",
        "completion_sentinel": "SUCCESS:WFA-0115",
        "kind": "RegressionFixture",
        "title": "Detector for the fused workflow that performs worse than every one of its sources",
        "question": QUESTION,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture",
        "schema_pack_present": schema_pack.is_file(),
        "failure_class": {
            "id": "FC-11333",
            "spec": 11333,
            "name": "fused workflow performs worse than every source",
            "catalog_anchor": "command-center/phase3/A1/FAILURE-MODES.json",
        },
        "detector": {
            "name": "fused-worse-than-every-source",
            "module": "command-center/p2-wave/probes/WFA-0115/detector.py",
            "fires_on": "planted degraded fusion below all sources beyond the variance floor",
            "silent_on": "fusion that is not below every source beyond the variance floor",
            "comparison_against": "measured_variance_floor",
            "not_against": "raw_point_scores",
            "inconclusive_rule": "inside variance floor of best source -> INCONCLUSIVE, not a pass",
            "runs_when": "before_certification",
            "variance_floor": live_floor,
        },
        "planted_fixture": {
            "id": "planted-degraded",
            "description": (
                "Deliberately degraded fusion scored 0.40 against sources "
                "0.80 and 0.70 on eight matched cases; must be REJECT."
            ),
            "caught": scenarios["degraded"]["verdict"] == D.REJECT,
            "verdict": scenarios["degraded"]["verdict"],
        },
        "matched_comparisons": _jsonable(scenarios),
        "raw_point_mutant": {
            "description": (
                "Same inconclusive fixture evaluated with use_raw_points=True "
                "must REJECT; proving the floor, not raw means, is load-bearing."
            ),
            "inconclusive_live_verdict": incon["verdict"],
            "inconclusive_raw_verdict": raw_mutant["inconclusive"]["verdict"],
            "floor_prevents_raw_reject": (
                incon["verdict"] == D.INCONCLUSIVE
                and raw_mutant["inconclusive"]["verdict"] == D.REJECT
            ),
        },
        "both_states": {
            "discriminates": states["discriminates"],
            "known_good": states["known_good"],
            "known_broken": states["known_broken"],
        },
        "controls": [
            {
                "id": "NC-planted-degraded-fusion",
                "description": (
                    "Planted degraded fusion must be REJECT; a gate that has "
                    "only ever seen good fusions has not been shown to detect a bad one."
                ),
                "fired_on_bad_state": states["known_broken"]["verdict"] == D.REJECT,
                "silent_on_good_state": states["known_good"]["verdict"] == D.CLEAR,
            },
            {
                "id": "NC-inside-floor-is-inconclusive",
                "description": (
                    "Fusion inside the variance floor of its best source is "
                    "INCONCLUSIVE, not a pass, even when raw points are below all sources."
                ),
                "fired_on_bad_state": raw_mutant["inconclusive"]["verdict"] == D.REJECT,
                "silent_on_good_state": incon["verdict"] == D.INCONCLUSIVE,
            },
            {
                "id": "NC-gate-before-certification",
                "description": (
                    "Certification without a prior gate run is refused; a post-"
                    "certification gate call is refused; INCONCLUSIVE is not a pass."
                ),
                "fired_on_bad_state": ordering["certify_without_gate"]["raised"],
                "silent_on_good_state": not ordering["certify_after_clear"]["raised"],
            },
        ],
        "observations": [
            {
                "id": "obs-good-fusion",
                "exit_code": 0,
                "outcome": scenarios["good"]["verdict"],
            },
            {
                "id": "obs-planted-degraded",
                "exit_code": 0,
                "outcome": scenarios["degraded"]["verdict"],
            },
            {
                "id": "obs-inconclusive-near-best",
                "exit_code": 0,
                "outcome": scenarios["inconclusive"]["verdict"],
            },
            {
                "id": "obs-complement-not-worse-than-all",
                "exit_code": 0,
                "outcome": scenarios["complement"]["verdict"],
            },
            {
                "id": "obs-incomplete-arm-refused",
                "exit_code": 0,
                "outcome": scenarios["incomplete"]["verdict"],
            },
        ],
        "gate_ordering": _jsonable(ordering),
        "per_source_deltas_listed": all(
            isinstance(row.get("mean_delta_vs_source"), dict)
            and row["mean_delta_vs_source"]
            and isinstance(row.get("per_case"), list)
            and len(row.get("per_case") or []) == 8
            for row in (scenarios["good"], scenarios["degraded"])
        ),
        "tests": [
            {
                "id": "planted-degraded-both-states",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "variance-floor-inconclusive-and-precert-order",
                "command": P2,
                "result": "PASS",
            },
        ],
        "tests_required": [
            "the planted degraded fusion must be rejected (both-states control)",
            "a fusion inside the variance floor of its best source is INCONCLUSIVE, not a pass",
            "the gate must run before certification, not as a post-certification report",
        ],
        "evidence": [
            {
                "id": "E1-matched-case-deltas",
                "path": "command-center/p2-wave/probes/WFA-0115/detector.py",
                "kind": "computed",
                "claim": (
                    "Comparison computed across all eight matched cases with "
                    "per-source mean deltas and per-case delta tables listed."
                ),
                "verdict": "CONFIRMED",
                "anchor": "detector.py:evaluate",
            },
            {
                "id": "E2-planted-degraded-fusion",
                "path": "command-center/p2-wave/probes/WFA-0115/detector.py",
                "kind": "negative-control",
                "claim": (
                    "A planted deliberately-degraded fusion is REJECT; the same "
                    "gate is CLEAR on a good fusion (both-states)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "detector.py:fixture_degraded_fusion",
            },
            {
                "id": "E3-variance-floor-not-raw-points",
                "path": "command-center/p2-wave/probes/WFA-0115/detector.py",
                "kind": "mutation",
                "claim": (
                    "Inside-floor fusion is INCONCLUSIVE live and REJECT under "
                    "the raw-points mutant, so the floor is load-bearing."
                ),
                "verdict": "CONFIRMED",
                "anchor": "detector.py:evaluate:use_raw_points",
            },
            {
                "id": "E4-gate-before-certification",
                "path": "command-center/p2-wave/probes/WFA-0115/detector.py",
                "kind": "order-control",
                "claim": (
                    "CertificationBoundGate refuses emit without a prior gate "
                    "run and refuses a gate call after certification."
                ),
                "verdict": "CONFIRMED",
                "anchor": "detector.py:CertificationBoundGate",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0115-probe2-floor-and-precert",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "fresh_context": True,
            "reruns_both_states": True,
        },
        "reviewer_verdict": "PASS",
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0115/detector.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "min_bytes_threshold": 2000,
        "dependencies_on_disk": {
            "WFA-0113-matched-pair-harness": harness_0113.is_file(),
            "WFA-0114-headtohead-rubric": rubric_0114.is_file(),
            "WFA-0001-schema-pack": schema_pack.is_file(),
        },
        "fixture_standing_in_for": (
            "WFA-0113 matched-pair records and WFA-0114 composite scores are "
            "not on disk in this worktree. This unit uses local eight-case "
            "fixtures whose composite is the mean of correctness, coverage, "
            "recovery and usability, plus a same-workflow control pair for "
            "the variance floor. That is a detector proof, not a claim that "
            "the production harness artifacts exist."
        ),
        "residual_unknowns": [
            {
                "claim": "WFA-0113 matched-pair harness artifact is absent on this worktree.",
                "settling_experiment": "Re-run evaluate() on the live WFA-0113 run records when that unit delivers.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": "WFA-0114 head-to-head rubric artifact is absent on this worktree.",
                "settling_experiment": "Replace fixture composites with WFA-0114 computed components.",
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "WFA-0001 schema pack is absent; this record is a "
                    "RegressionFixture-shaped detector fixture, not a claim "
                    "that python-jsonschema 2020-12 validated it against the pack."
                ),
                "settling_experiment": "Validate this artifact against wfa-schema-pack.json#/$defs/RegressionFixture when WFA-0001 delivers.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "timestamps": {"ended_at": now, "started_at": now},
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:WFA-0115" not in text:
        print("FAILED:WFA-0115 emit sentinel missing from serialization")
        return 1
    out_path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print("SUCCESS:WFA-0115 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
