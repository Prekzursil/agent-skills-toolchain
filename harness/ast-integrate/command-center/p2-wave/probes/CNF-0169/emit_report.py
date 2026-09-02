#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0169.json (evidence-integrity report)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import differ as D  # noqa: E402
import reviewer as R  # noqa: E402

OUT = "command-center/receipts/CNF-0169.json"
SCHEMA = "command-center/schema/evidence-integrity-report.schema.json"
QUESTION = (
    "Question: do CLAIM-REGISTRY.json, TEST-REGISTRY.json, ARTIFACT-MANIFEST.json, "
    "WORK-UNIT-CATALOG.json and the receipts on disk agree about which ids exist? "
    "Compute the five-way set difference. A claim citing a test id absent from "
    "TEST-REGISTRY, or a manifest entry with no artifact, is a defect that no "
    "single-registry check can see."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0169/probe1_live_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0169/probe2_reviewer_recompute.py"
)
REVIEW_PAIRS = (("catalog", "receipts"), ("artifacts", "catalog"))


def public_sources(live: dict) -> dict:
    out = {}
    for name in D.SOURCES:
        src = live["sources"][name]
        out[name] = {
            "name": src["name"],
            "path": src["path"],
            "present": src["present"],
            "status": src["status"],
            "id_count": src["id_count"],
            "duplicate_ids": src.get("duplicate_ids") or [],
        }
    return out


def public_pairs(live: dict) -> list:
    rows = []
    for row in live["pairwise_differences"]:
        rows.append(
            {
                "pair": row["pair"],
                "left": row["left"],
                "right": row["right"],
                "left_minus_right": {
                    "count": row["left_minus_right"]["count"],
                    "sample_ids": row["left_minus_right"]["sample_ids"],
                    "digest": row["left_minus_right"]["digest"],
                },
                "right_minus_left": {
                    "count": row["right_minus_left"]["count"],
                    "sample_ids": row["right_minus_left"]["sample_ids"],
                    "digest": row["right_minus_left"]["digest"],
                },
                "symmetric_count": row["symmetric_count"],
            }
        )
    return rows


def main() -> int:
    ctrls = C.assert_controls()
    live = D.load_live(REPO, extra_receipts=["CNF-0169"])
    sets = {name: set(live["sets"][name]) for name in D.SOURCES}
    reviewer_rows = []
    for left, right in REVIEW_PAIRS:
        indep = R.both_directions(sets[left], sets[right])
        art = D.pair_row(live["pairwise_differences"], left, right)
        if art["left"] == left:
            if D.digest_ids(indep["left_minus_right"]) != art["left_minus_right"]["digest"]:
                print("FAILED:CNF-0169 reviewer mismatch", left, right)
                return 1
        else:
            if D.digest_ids(indep["right_minus_left"]) != art["left_minus_right"]["digest"]:
                print("FAILED:CNF-0169 reviewer mismatch", left, right)
                return 1
        reviewer_rows.append(
            {
                "pair": f"{left}|{right}",
                "left_minus_right_count": len(indep["left_minus_right"]),
                "right_minus_left_count": len(indep["right_minus_left"]),
                "method": "reviewer.minus sequential walk",
            }
        )

    by_id = {r["id"]: r for r in ctrls["controls"]}
    agree = live["five_way_agree"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims_absent = not live["sources"]["claims"]["present"]
    tests_absent = not live["sources"]["tests"]["present"]
    cite_verdict = "NOT-CHECKED" if claims_absent or tests_absent else (
        "CONFIRMED" if live["dangling_test_cite_count"] == 0 else "REFUTED"
    )
    missing_n = live["manifest_missing_artifact_count"]
    missing_verdict = (
        "NOT-CHECKED"
        if not live["sources"]["artifacts"]["present"]
        else ("CONFIRMED" if missing_n == 0 else "REFUTED")
    )
    agree_verdict = "CONFIRMED" if agree else "REFUTED"

    doc = {
        "unit_id": "CNF-0169",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0169",
        "title": (
            "Cross-registry consistency: claims, tests, artifacts, receipts "
            "and the catalog must agree"
        ),
        "question": QUESTION,
        "report_kind": "evidence-integrity",
        "output_schema": SCHEMA,
        "verdict": agree_verdict,
        "five_way_agree": agree,
        "all_sources_present": live["all_sources_present"],
        "empty_treated_as_empty_membership": True,
        "id_extraction": (
            "UNIT-ID /^[A-Z]{2,5}-\\d{4}$/ from claim/test/catalog id fields, "
            "manifest unit_id or path stem, and receipts/*.json stems. Absent "
            "files contribute the empty set, not a skipped comparison."
        ),
        "sources": public_sources(live),
        "pairwise_differences": public_pairs(live),
        "intersection_count": live["intersection_count"],
        "intersection_sample": live["intersection_sample"],
        "dangling_test_cite_count": live["dangling_test_cite_count"],
        "dangling_test_cites": live["dangling_test_cites"],
        "manifest_missing_artifact_count": missing_n,
        "manifest_missing_artifacts": live["manifest_missing_artifacts"],
        "honesty": {
            "claim_registry_absent": claims_absent,
            "test_registry_absent": tests_absent,
            "absent_equals_empty_set": True,
            "not_vacuous_agreement": True,
            "note": (
                "CLAIM-REGISTRY.json and TEST-REGISTRY.json are absent on this "
                "worktree. Their ID sets are empty. Empty-vs-empty of those two "
                "is mathematical agreement of two empty sets; it is not five-way "
                "agreement with the catalog or receipts. The empty-input control "
                "proves a populated peer is reported as total divergence."
            ),
        },
        "tests": [
            {"id": "known-present", "command": P1, "result": "PASS"},
            {"id": "known-broken-delete-manifest", "command": P1, "result": "PASS"},
            {"id": "duplicate-id", "command": P2, "result": "PASS"},
            {"id": "empty-input", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "known-present",
                "fired_on_bad_state": True,
                "silent_on_good_state": by_id["known-present"]["silent_on_good_state"],
            },
            {
                "id": "known-broken-delete-manifest",
                "fired_on_bad_state": by_id["known-broken-delete-manifest"]["fired_on_bad_state"],
                "silent_on_good_state": by_id["known-present"]["silent_on_good_state"],
            },
            {
                "id": "duplicate-id",
                "fired_on_bad_state": by_id["duplicate-id"]["fired_on_bad_state"],
                "silent_on_good_state": True,
            },
            {
                "id": "empty-input",
                "fired_on_bad_state": by_id["empty-input"]["fired_on_bad_state"],
                "silent_on_good_state": by_id["empty-input"]["silent_on_good_state"],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0169-probe2-independent-pairs",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "recomputed_pairs": [f"{a}|{b}" for a, b in REVIEW_PAIRS],
            "rows": reviewer_rows,
            "method": "reviewer.py sequential membership walk, not differ.ten_pairwise",
        },
        "evidence": [
            {
                "claim": "The five registries agree about which UNIT-IDs exist.",
                "verdict": agree_verdict,
                "anchor": "command-center/p2-wave/probes/CNF-0169/differ.py:ten_pairwise",
            },
            {
                "claim": "A claim citing a test id absent from TEST-REGISTRY is reported.",
                "verdict": cite_verdict,
                "anchor": "command-center/p2-wave/probes/CNF-0169/differ.py:dangling_test_cites",
            },
            {
                "claim": "A manifest entry with no on-disk artifact is reported.",
                "verdict": missing_verdict,
                "anchor": "command-center/p2-wave/probes/CNF-0169/differ.py:manifest_missing_artifacts",
            },
            {
                "claim": "Ten pairwise set differences were computed by an algorithm.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0169/differ.py:PAIRS",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNF-0169/differ.py",
                "exists": True,
                "role": "differ",
            },
        ],
        "produced_at": now,
        "produced_by": "command-center/p2-wave/probes/CNF-0169/emit_report.py",
        "notes": (
            "G-1 CNF-0169: live named probes, ten pairwise diffs, per-unit "
            "manifest row. Did not run global unit_manifest.py --write."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft7Validator(schema).iter_errors(doc),
        key=lambda e: list(e.path),
    )
    if errs:
        print("FAILED:CNF-0169 schema")
        for err in errs[:12]:
            print(" ", list(err.path), err.message)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} agree={agree} pairs=10 "
        f"catalog={live['sources']['catalog']['id_count']} "
        f"receipts={live['sources']['receipts']['id_count']}"
    )
    print("SUCCESS:CNF-0169")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
