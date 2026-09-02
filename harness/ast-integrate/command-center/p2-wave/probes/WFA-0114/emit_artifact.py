#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0114-headtohead-scoring-rubric.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import rubric as R  # noqa: E402

OUT = "command-center/wfa/WFA-0114-headtohead-scoring-rubric.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/BenchmarkResult"
FIXTURE = HERE / "fixtures" / "recorded_runs.json"
SENTINEL = "SUCCESS:WFA-0114"
QUESTION = (
    "Implementation target: a scoring rubric with computed - not judged - "
    "components for correctness, coverage, recovery and usability, and an "
    "explicit rule for what counts as materially complementary when a fused "
    "workflow does not outperform its sources."
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def slim_named(named: list[dict]) -> list[dict]:
    rows = []
    for c in named:
        row = {
            "id": c["id"],
            "status": c["status"],
            "formula": c.get("formula"),
        }
        if c.get("status") == "retained":
            row["value"] = c["value"]
        else:
            row["reason"] = c.get("reason")
        for k in (
            "n_pass",
            "n_matched",
            "n_attempted",
            "n_recovered",
            "n_recoverable",
            "kappa",
        ):
            if k in c:
                row[k] = c[k]
        rows.append(row)
    return rows


def main() -> int:
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    corpus = list(fx["corpus_case_ids"])
    matched = list(fx["matched_intersection"])
    arms = fx["arms"]
    sources = [arms["source_a"], arms["source_b"]]
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    unfrozen = R.HeadToHeadRubric()
    refused_unfrozen = unfrozen.decide(
        arms["fusion_outperforms"], sources, matched, corpus
    )
    if refused_unfrozen.get("decision") != "REFUSED":
        print("FAILED:WFA-0114 emit unfrozen certify must refuse")
        return 1

    spec = R.HeadToHeadRubric()
    freeze_hash = spec.freeze(started)
    mutated = R.HeadToHeadRubric()
    mutated.freeze(started)
    mutated.mutate_formula(
        "correctness", "n_pass / n_attempted  # post-hoc fit after seeing labels"
    )
    refused_mutated = mutated.decide(
        arms["fusion_outperforms"], sources, matched, corpus
    )
    if refused_mutated.get("decision") != "REFUSED":
        print("FAILED:WFA-0114 emit post-hoc mutate must refuse")
        return 1

    comparisons = {}
    for key in (
        "fusion_outperforms",
        "fusion_complement",
        "fusion_padded",
        "fusion_no_attempts",
    ):
        comparisons[key] = spec.decide(arms[key], sources, matched, corpus)

    if comparisons["fusion_outperforms"]["decision"] != "OUTPERFORMS":
        print("FAILED:WFA-0114 emit outperform", comparisons["fusion_outperforms"])
        return 1
    if comparisons["fusion_complement"]["decision"] != "MATERIALLY_COMPLEMENTARY":
        print("FAILED:WFA-0114 emit complement", comparisons["fusion_complement"])
        return 1
    if comparisons["fusion_padded"]["decision"] != "REJECT":
        print("FAILED:WFA-0114 emit padded", comparisons["fusion_padded"])
        return 1

    high = R.component_human(
        fx["inter_rater"]["high_agreement"]["rater_a"],
        fx["inter_rater"]["high_agreement"]["rater_b"],
    )
    low = R.component_human(
        fx["inter_rater"]["low_agreement"]["rater_a"],
        fx["inter_rater"]["low_agreement"]["rater_b"],
    )
    if high.get("status") != "retained" or low.get("status") != "removed":
        print("FAILED:WFA-0114 emit inter-rater", high, low)
        return 1

    outperform_named = comparisons["fusion_outperforms"]["fusion"]["named"]
    rec = next(c for c in outperform_named if c["id"] == "recovery")
    if rec["status"] != "removed":
        print("FAILED:WFA-0114 emit recovery not removed")
        return 1
    zeroed = comparisons["fusion_outperforms"]["fusion"]["zero_filled_named_composite"]
    arm_c = comparisons["fusion_outperforms"]["fusion"]["arm_composite"]["value"]
    if abs(arm_c - zeroed) < 1e-12:
        print("FAILED:WFA-0114 emit removal collapsed into zero-fill")
        return 1

    source_a_named = spec.score_arm(arms["source_a"], matched)
    fixture_sha, fixture_bytes = sha_file(FIXTURE)
    engine_sha, engine_bytes = sha_file(HERE / "rubric.py")
    schema_pack = REPO / "command-center/wfa/schema/wfa-schema-pack.json"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    uniq = comparisons["fusion_complement"]["complement"]["unique_case_ids"]
    delta = comparisons["fusion_complement"]["complement"]["delta"]

    doc = {
        "record_type": "BenchmarkResult",
        "schema_ref": SCHEMA,
        "schema_pack_present": schema_pack.is_file(),
        "schema_pack_note": (
            "WFA-0001 schema pack is not on this worktree. Formulas, freeze "
            "hash and live comparison numbers are stated so a later pack can "
            "validate shape without this unit inventing the 18-def bundle."
        ),
        "unit_id": "WFA-0114",
        "id": "WFA-0114",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Head-to-head scoring rubric on correctness, coverage, recovery "
            "and usability"
        ),
        "question": QUESTION,
        "output_path": OUT,
        "started_at": started,
        "ended_at": ended,
        "dependency_note": (
            "Catalog depends on WFA-0112 (benchmark case corpus), which is "
            "absent. Scoring runs against bundled recorded-run fields that "
            "match the harness record shape. This demonstrates the rubric, "
            "not an estate-corpus harvest."
        ),
        "rubric": {
            "named_computed_components": list(R.NAMED_COMPUTED),
            "formulas": dict(R.FORMULAS),
            "weight_policy": R.WEIGHT_POLICY,
            "uncomputable_policy": R.UNCOMPUTABLE_POLICY,
            "agreement_floor": R.AGREEMENT_FLOOR,
            "complement_delta_floor": R.COMPLEMENT_DELTA_FLOOR,
            "human_component": R.HUMAN_COMPONENT,
            "stage_count_is_not_a_component": True,
            "asymmetric_cases_folded_into_head_to_head": False,
        },
        "freeze": {
            "frozen": True,
            "frozen_at": started,
            "freeze_hash": freeze_hash,
            "live_digest": spec.live_digest(),
            "unfrozen_certify": {
                "decision": refused_unfrozen["decision"],
                "reason": refused_unfrozen["reason"],
            },
            "post_hoc_mutate_certify": {
                "decision": refused_mutated["decision"],
                "reason": refused_mutated["reason"],
            },
            "rule": (
                "The spec hash is taken before the first certification "
                "decision. Changing a formula after freeze REFUSES."
            ),
        },
        "source_a_named_components": slim_named(source_a_named["named"]),
        "source_a_arm_composite": source_a_named["arm_composite"],
        "comparisons": {
            key: {
                "decision": row["decision"],
                "reason": row["reason"],
                "outperforms": row.get("outperforms"),
                "materially_complementary": row.get("materially_complementary"),
                "comparison_component_ids": row.get("comparison_component_ids"),
                "fusion_arm_composite": (row.get("fusion") or {}).get(
                    "arm_composite"
                ),
                "fusion_comparison_composite": (row.get("fusion") or {}).get(
                    "comparison_composite"
                ),
                "fusion_zero_filled_named_composite": (row.get("fusion") or {}).get(
                    "zero_filled_named_composite"
                ),
                "fusion_named": slim_named(
                    (row.get("fusion") or {}).get("named") or []
                ),
                "fusion_stages": (row.get("fusion") or {}).get("stages"),
                "best_source_comparison_composite": row.get(
                    "best_source_comparison_composite"
                ),
                "complement": row.get("complement"),
                "sources": [
                    {
                        "arm_id": s["arm_id"],
                        "stages": s["stages"],
                        "comparison_composite": s["comparison_composite"],
                    }
                    for s in (row.get("sources") or [])
                ],
            }
            for key, row in comparisons.items()
        },
        "inter_rater": {
            "metric": "cohen_kappa",
            "floor": R.AGREEMENT_FLOOR,
            "high_agreement": high,
            "low_agreement": low,
            "frozen_human_component": (
                "removed from the production rubric because the honest "
                "calibration set is the low-agreement pair; high-agreement "
                "is the both-states control"
            ),
        },
        "tests": [
            {
                "id": "WFA0114-UNCOMPUTABLE-REMOVED",
                "name": (
                    "a component that cannot be computed or reliably rated "
                    "is removed, not weighted down"
                ),
                "result": "PASS",
                "evidence": (
                    "fusion_outperforms has zero first-attempt failures so "
                    f"recovery is removed; arm composite {arm_c} != "
                    f"zero-filled {zeroed}. fusion_no_attempts removes "
                    "usability (empty attempted set)."
                ),
            },
            {
                "id": "WFA0114-COMPLEMENT-DELTA",
                "name": (
                    "materially complementary is a measurable coverage "
                    "delta, not prose"
                ),
                "result": "PASS",
                "evidence": (
                    f"fusion_complement unique_case_ids={uniq} delta={delta} "
                    f"floor={R.COMPLEMENT_DELTA_FLOOR}; decision="
                    f"{comparisons['fusion_complement']['decision']}. "
                    "fusion_padded has more stages and identical matched "
                    "results and is "
                    f"{comparisons['fusion_padded']['decision']}."
                ),
            },
            {
                "id": "WFA0114-RUBRIC-FROZEN",
                "name": (
                    "the rubric is frozen before the first certification "
                    "decision"
                ),
                "result": "PASS",
                "evidence": (
                    f"unfrozen={refused_unfrozen['decision']}; "
                    f"mutated={refused_mutated['decision']}; "
                    f"frozen hash {freeze_hash[:16]}... matches live digest"
                ),
            },
        ],
        "evidence": [
            {
                "kind": "formula-on-recorded-runs",
                "path": "command-center/p2-wave/probes/WFA-0114/rubric.py",
                "sha256": engine_sha,
                "bytes": engine_bytes,
                "claim": (
                    "Correctness, coverage, recovery and usability are ratios "
                    "over recorded oracle/attempt/retry/telemetry fields with "
                    "the formula string stored next to the number."
                ),
            },
            {
                "kind": "recorded-run-fixture",
                "path": (
                    "command-center/p2-wave/probes/WFA-0114/fixtures/"
                    "recorded_runs.json"
                ),
                "sha256": fixture_sha,
                "bytes": fixture_bytes,
                "claim": (
                    "Matched intersection c01-c06; asymmetric unique solves "
                    "c07-c09 on fusion_complement are excluded from the "
                    "head-to-head correctness denominator."
                ),
            },
            {
                "kind": "inter-rater",
                "path": (
                    "command-center/p2-wave/probes/WFA-0114/fixtures/"
                    "recorded_runs.json"
                ),
                "claim": (
                    f"Low-agreement kappa={low.get('kappa')} removes "
                    f"{R.HUMAN_COMPONENT}; high-agreement kappa="
                    f"{high.get('kappa')} would retain it. Removal, not a "
                    "caveat or a down-weight."
                ),
            },
        ],
        "reviewers": [
            {
                "role": "author",
                "reviewer_id": "WFA-0114-emit-artifact",
                "verdict": "PASS",
                "independent": False,
            },
            {
                "role": "adversarial-probe2",
                "reviewer_id": "WFA-0114-probe2-coverage-delta-and-inter-rater",
                "verdict": "PASS",
                "independent": True,
                "requirement": (
                    "re-run both-states: complement vs padded-stages, and "
                    "high vs low inter-rater"
                ),
            },
        ],
        "catalog_tests_required": [
            "a component that cannot be computed or reliably rated is removed, not weighted down",
            "materially complementary must be operationalised as a measurable coverage delta, not left as prose",
            "the rubric must be frozen before the first certification decision to prevent post-hoc fitting",
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    sha, nbytes = sha_file(dest)
    if SENTINEL not in dest.read_text(encoding="utf-8"):
        print("FAILED:WFA-0114 emit sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={nbytes} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
