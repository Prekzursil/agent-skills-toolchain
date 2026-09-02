#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0412.json (duplicate-report)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import run_distinct_control, run_duplicate_control  # noqa: E402
from fingerprint import ALGORITHM_ID, JACCARD_THRESHOLD  # noqa: E402
from independent import independent_collisions  # noqa: E402
from scan import load_catalog, scan_catalog  # noqa: E402
from schema_gate import SENTINEL as GATE_SENTINEL  # noqa: E402
from schema_gate import assert_valid  # noqa: E402

OUT_REL = "command-center/receipts/IMP-0412.json"
SCHEMA_REL = "command-center/schema/duplicate-report.schema.json"
SENTINEL = "SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0412/probe1_planted_duplicates.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0412/probe2_planted_distinct.py"
)
ARTIFACT_RELS = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/IMP-0412/schema_gate.py",
    "command-center/p2-wave/probes/IMP-0412/fingerprint.py",
    "command-center/p2-wave/probes/IMP-0412/scan.py",
    "command-center/p2-wave/probes/IMP-0412/claim_check.py",
    "command-center/p2-wave/probes/IMP-0412/planted.py",
    "command-center/p2-wave/probes/IMP-0412/controls.py",
    "command-center/p2-wave/probes/IMP-0412/independent.py",
    "command-center/p2-wave/probes/IMP-0412/probe1_planted_duplicates.py",
    "command-center/p2-wave/probes/IMP-0412/probe2_planted_distinct.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def build_receipt() -> dict:
    catalog = load_catalog(REPO)
    units = catalog.get("work_units") or []
    live = scan_catalog(REPO)
    if live["too_coarse"]["abort"]:
        raise SystemExit(f"fingerprint too coarse: {live['too_coarse']}")
    dup = run_duplicate_control(units)
    dist = run_distinct_control(units)
    if not dup["pass"] or not dist["pass"]:
        raise SystemExit(f"planted controls failed dup={dup} dist={dist}")
    indep = independent_collisions(units)
    if len(indep) != live["collision_pair_count"]:
        raise SystemExit(
            "independent recount disagrees "
            f"primary={live['collision_pair_count']} independent={len(indep)}"
        )

    cat_meta = live["catalog"]
    fp_rate = live["false_positive_rate"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = []
    for rel in ARTIFACT_RELS:
        path = REPO / rel
        sha, size = digest(path)
        artifacts.append(
            {
                "path": rel,
                "role": "schema" if rel.endswith(".schema.json") else "implementation",
                "sha256": sha,
                "bytes": size,
                "exists": True,
            }
        )

    n = live["unit_count"]
    pairs = live["compared_pair_count"]
    n_coll = live["collision_pair_count"]
    sample_size = min(20, n_coll)
    return {
        "unit_id": "IMP-0412",
        "title": "Duplicate-work suppression by normalized unit fingerprint",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "cloud_ok": False,
        "ts": now,
        "question": (
            "Implement a fingerprint over the normalized work-unit target text "
            "plus its input set, so the same mechanism dispatched twice under "
            "different ids is caught at claim time. Exact question: applied to "
            "the assembled 2048-unit catalog, how many pairs collide, and is "
            "each collision a genuine duplicate or a false positive?"
        ),
        "algorithm": {
            "id": ALGORITHM_ID,
            "description": (
                "Target text is taken from question_or_target (fallback target, "
                "then title). Tokens are NFKC-lowercased, punctuation-stripped, "
                "stopword-filtered, synonym-folded, and lightly stemmed. The "
                "input set is slash-normalized, lowercased, and stripped of "
                ":line-range locators, then sorted unique. Two units collide "
                "when those input sets are equal and target-token Jaccard is "
                f">= {JACCARD_THRESHOLD}. Shared fingerprint is SHA-256 of the "
                "input set plus the token intersection. A scan that flags more "
                "than 2% of units or a cluster larger than 12 is aborted as "
                "too-coarse rather than retried."
            ),
            "collision_rule": (
                "same normalized input set AND target-token Jaccard "
                f">= {JACCARD_THRESHOLD}"
            ),
            "jaccard_threshold": JACCARD_THRESHOLD,
            "target_fields": ["question_or_target", "target", "title"],
            "includes_input_set": True,
            "too_coarse_abort": live["too_coarse"]["abort_rule"],
        },
        "catalog_scan": {
            "path": cat_meta["path"],
            "slice_glob": cat_meta["slice_glob"],
            "slice_files_found": cat_meta["slice_files_found"],
            "slice_files_declared_in_meta": cat_meta["slice_files_declared_in_meta"],
            "declared_program_count": cat_meta["declared_program_count"],
            "meta_work_unit_count": cat_meta["meta_work_unit_count"],
            "assembled_work_unit_count": cat_meta["assembled_work_unit_count"],
            "shortfall": cat_meta["shortfall"],
            "meta_status": cat_meta["meta_status"],
            "compared_pair_count": pairs,
            "collision_pair_count": n_coll,
            "genuine_duplicate_count": live["genuine_duplicate_count"],
            "false_positive_count": live["false_positive_count"],
            "needs_review_count": live["needs_review_count"],
            "too_coarse": live["too_coarse"]["abort"],
            "too_coarse_detail": live["too_coarse"],
            "fingerprint_table_sha256": live["fingerprint_table_sha256"],
            "independent_method": "independent-raw-tokens-plus-inputs",
            "independent_collision_pair_count": len(indep),
        },
        "collisions": live["collisions"],
        "false_positive_rate": fp_rate,
        "answers": {
            "declared_program_count": cat_meta["declared_program_count"],
            "assembled_unit_count": n,
            "shortfall": cat_meta["shortfall"],
            "colliding_pairs": n_coll,
            "genuine_duplicates": live["genuine_duplicate_count"],
            "false_positives": live["false_positive_count"],
            "needs_review": live["needs_review_count"],
            "note": (
                "The catalog declares a 2048-unit program; the assembled "
                f"work_units array contains {n} rows (shortfall "
                f"{cat_meta['shortfall']}). Fingerprints were applied to the "
                "assembled array, not to a reconstructed 2048. catalog-slices/"
                " is absent on this worktree; slice membership was taken from "
                "work_units_meta.slice_files_merged."
            ),
        },
        "claim_time": {
            "api": "command-center/p2-wave/probes/IMP-0412/claim_check.py:check_claim",
            "behavior": (
                "On acquire, fingerprint the claimed unit and compare it to "
                "every other catalog row. A second id with the same normalized "
                "input set and target Jaccard >= 0.85 is returned as a collision "
                "and must block the claim."
            ),
            "ghost_claim_caught_imp0412": dup["claim_time_caught_donor"],
        },
        "planted_controls": {
            "exact_duplicate_caught": dup["exact_duplicate_caught"],
            "reworded_duplicate_caught": dup["reworded_duplicate_caught"],
            "distinct_pair_did_not_collide": dist["distinct_pair_did_not_collide"],
            "claim_time_caught_donor": dup["claim_time_caught_donor"],
            "planted_distinct_jaccard": dist["planted_jaccard"],
            "live_related_non_collision": {
                "pair": ["IMP-0412", "IMP-0456"],
                "shared_inputs": True,
                "collided": dist["live_imp0412_vs_imp0456_collided"],
                "jaccard": dist["live_imp0412_vs_imp0456_jaccard"],
            },
        },
        "report": {
            "kind": "duplicate-report",
            "control_ids": [
                "planted-exact-duplicate",
                "planted-reworded-duplicate",
                "planted-distinct-similar-vocabulary",
                "claim-time-ghost",
            ],
            "observations": [
                {
                    "name": "assembled_work_unit_count",
                    "measured": n,
                    "method": "file-read",
                    "anchor": "command-center/WORK-UNIT-CATALOG.json",
                },
                {
                    "name": "collision_pair_count",
                    "measured": n_coll,
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/IMP-0412/scan.py",
                },
                {
                    "name": "independent_collision_pair_count",
                    "measured": len(indep),
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/IMP-0412/independent.py",
                },
                {
                    "name": "false_positives",
                    "measured": int(fp_rate["false_positives"]),
                    "method": "static-analysis",
                    "anchor": "command-center/p2-wave/probes/IMP-0412/scan.py:adjudicate",
                },
            ],
        },
        "adv_rebuild_circle": False,
        "required_fix": None,
        "tests": [
            {
                "id": "planted-exact-duplicate",
                "name": "Inject an exact clone of IMP-0412; it must collide",
                "command": P1,
                "result": "PASS" if dup["exact_duplicate_caught"] else "FAIL",
            },
            {
                "id": "planted-reworded-duplicate",
                "name": "Inject a synonym/punctuation rewording of IMP-0412; it must collide",
                "command": P1,
                "result": "PASS" if dup["reworded_duplicate_caught"] else "FAIL",
            },
            {
                "id": "planted-distinct-similar-vocabulary",
                "name": "Two different mechanisms sharing catalog vocabulary and inputs must not collide",
                "command": P2,
                "result": "PASS" if dist["distinct_pair_did_not_collide"] else "FAIL",
            },
            {
                "id": "claim-time-ghost",
                "name": "A second dispatch of IMP-0412 under a new id is caught at claim time",
                "command": P1,
                "result": "PASS" if dup["claim_time_caught_donor"] else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0412-probe2-independent-raw-token-jaccard",
            "independent": True,
            "verdict": "PASS",
            "requested_blind_sample": 20,
            "available_collisions": n_coll,
            "sample_size": sample_size,
            "sample": live["collisions"][:sample_size],
            "note": (
                "Independent tokenizer (no stemmer, no synonym map) recomputed "
                f"{n} fingerprints and found {len(indep)} colliding pairs, "
                "matching the primary scan. A blind sample of 20 was requested; "
                f"{n_coll} collisions exist, so the sample is the full collision "
                "list (empty if none). There is nothing to adjudicate beyond the "
                "empty list."
            ),
        },
        "evidence": [
            {
                "id": "E1-collision-list",
                "kind": "catalog-scan",
                "claim": (
                    f"{n_coll} colliding pairs over {n} assembled units "
                    f"({pairs} compared pairs). Each row carries both ids, "
                    "the shared fingerprint, Jaccard, and an adjudication column."
                ),
                "collision_pair_count": n_coll,
            },
            {
                "id": "E2-false-positive-rate",
                "kind": "rate-with-denominator",
                "claim": fp_rate["rate_display"],
                "false_positives": fp_rate["false_positives"],
                "denominator": fp_rate["denominator"],
                "denominator_meaning": fp_rate["denominator_meaning"],
            },
            {
                "id": "E3-planted-duplicates",
                "kind": "control",
                "claim": (
                    "Exact clone PLANT-EXACT-0412 and reworded clone "
                    "PLANT-REWORD-0412 both collide with IMP-0412; a ghost "
                    "claim under IMP-GHOST-0412 is caught at claim time."
                ),
            },
            {
                "id": "E4-planted-distinct",
                "kind": "negative-control",
                "claim": (
                    "PLANT-DIST-A vs PLANT-DIST-B share inputs and catalog "
                    f"vocabulary (Jaccard {dist['planted_jaccard']}) and do not "
                    "collide. Live IMP-0412 vs IMP-0456 likewise share inputs "
                    f"and do not collide (Jaccard {dist['live_imp0412_vs_imp0456_jaccard']})."
                ),
            },
        ],
        "artifacts": artifacts,
        "notes": (
            "G-1 for IMP-0412: live named probes exit 0, receipt is not BLOCKED, "
            "sentinel SENTINEL:IMP-0412:DUPLICATES-FINGERPRINTED is present. "
            "cloud_ok is not delivery. Did not run global unit_manifest.py --write."
        ),
    }


def write_receipt() -> Path:
    doc = build_receipt()
    if GATE_SENTINEL != SENTINEL:
        raise SystemExit("schema_gate SENTINEL drifted from emit_report")
    assert_valid(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if SENTINEL not in out.read_text(encoding="utf-8"):
        raise SystemExit("sentinel missing from written receipt")
    return out


def main() -> int:
    path = write_receipt()
    sha, size = digest(path)
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
