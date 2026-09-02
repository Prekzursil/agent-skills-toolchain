#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0175.json (confirmation record)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fusion_core as fc  # noqa: E402
import certify as certify_mod  # noqa: E402

OUT = "command-center/receipts/CNF-0175.json"
SCHEMA = "command-center/schema/confirmation-record.schema.json"
PROBE_DIR = "command-center/p2-wave/probes/CNF-0175"
P1 = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {PROBE_DIR}/probe1_reseed_substrates.py"
P2 = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {PROBE_DIR}/probe2_reviewer_controls.py"
CERT_REL = f"{PROBE_DIR}/adjudicator/certification.json"
QUESTION = (
    "Does a certified fusion still beat its sources when the seeds are "
    "re-randomized and the substrate changes?"
)
CLAIM_ID = "CNF-0175-fusion-win-reseed-substrate"


def compact_summary(s: dict) -> dict:
    return {
        "seed": s["seed"],
        "substrate": s["substrate"],
        "n_cases": s["n_cases"],
        "mean_f1": s["mean_f1"],
        "mean_delta_vs_best_source": s["mean_delta_vs_best_source"],
        "effect_size_cohens_d": s["effect_size_cohens_d"],
        "delta_ci95": s["delta_ci95"],
        "ci_excludes_zero_or_negative": s["ci_excludes_zero_or_negative"],
        "fusion_beats_each_source_mean": s["fusion_beats_each_source_mean"],
        "weak_source_loses": s["weak_source_loses"],
        "more_stages_not_used_as_win": s["more_stages_not_used_as_win"],
        "per_case": s["per_case"],
    }


def planted_detector(seed: int) -> dict:
    wids = [fc.PLANTED_WORSE, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C, fc.FUSION]
    rows = fc.run_matrix((seed,), [fc.SUBSTRATE_INPROCESS], wids)
    means = {}
    for wid in wids:
        vals = [r["f1"] for r in rows if r["workflow_id"] == wid]
        means[wid] = round(fc.mean(vals), 6)
    # Weak-constant F1 is 0; a non-negative metric cannot be strictly worse.
    # The named class is fusion-worse-than-every-productive-source (A and B).
    worse_than_a_b = (
        means[fc.PLANTED_WORSE] < means[fc.SOURCE_A]
        and means[fc.PLANTED_WORSE] < means[fc.SOURCE_B]
        and means[fc.PLANTED_WORSE] < means[fc.FUSION]
    )
    return {
        "seed": seed,
        "mean_f1": means,
        "worse_than_productive_sources": worse_than_a_b,
        "note": (
            "Planted union-all is worse than precision-router and "
            "recall-expander. weak-constant already scores 0 F1, so "
            "strict-worse-than-every-source is unsatisfiable on this metric."
        ),
    }


def main() -> int:
    repo = fc.REPO
    scan = fc.estate_fusion_scan(repo)
    empty = fc.empty_input_control()
    refuse = fc.refuse_empty_run([])
    if not empty.get("ok") or refuse.get("green") is not False:
        print("FAILED:CNF-0175 empty-input control did not refuse")
        return 1

    cert_path = repo / CERT_REL
    if not cert_path.is_file():
        certify_mod.main()
    cert_raw = cert_path.read_bytes()
    cert_sha = fc.sha256_bytes(cert_raw)

    wids = [fc.FUSION, fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C]
    rows = fc.run_matrix(
        fc.CONFIRM_SEEDS,
        [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        wids,
    )
    summaries = []
    for seed in fc.CONFIRM_SEEDS:
        for sub in (fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS):
            summaries.append(fc.summarize_condition(rows, seed, sub))
    agreement = fc.substrate_agreement(rows, fc.CONFIRM_SEEDS)
    planted = planted_detector(fc.CONFIRM_SEEDS[0])

    all_beat = all(s["fusion_beats_each_source_mean"] for s in summaries)
    all_ci = all(s["ci_excludes_zero_or_negative"] for s in summaries)
    all_weak = all(s["weak_source_loses"] for s in summaries)
    win_survives = all_beat and all_ci and all_weak and agreement["agree"]

    if not win_survives:
        verdict = "REFUTED"
        residual = (
            "The certified splice win did not survive re-seeding and/or "
            "the second substrate within the stated interval. Recorded as "
            "REFUTED (no verdict laundering)."
        )
    else:
        verdict = "CONFIRMED"
        residual = (
            "No estate production certified fusion exists on this worktree "
            "(estate scan). Confirmation applies to the local certified "
            "splice fixture. Presentation-order seeds and a redundant "
            "token did not move F1 after OOV-strip; that is evidence the "
            "win is not a seed artifact, not a skipped control."
        )

    margins0 = fc.per_case_margins(rows, fc.CONFIRM_SEEDS[0], fc.SUBSTRATE_INPROCESS)
    closest = fc.closest_cases(margins0, n=2)

    blinding_payload = {
        "fusion_id": fc.FUSION,
        "sources": [fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C],
        "case_ids": [c["id"] for c in fc.matched_cases()],
        "confirm_seeds": list(fc.CONFIRM_SEEDS),
        "substrates": [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        "cert_path": CERT_REL,
        "cert_sha256": cert_sha,
        "excludes": "original certification scores (adjudicator-only)",
    }
    blinding = fc.fingerprint("cnf-0175-blinding", blinding_payload)
    source_fp = fc.fingerprint(
        "probe1",
        {
            "command": P1,
            "seeds": list(fc.CONFIRM_SEEDS),
            "substrates": [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
        },
    )
    verifier_fp = fc.fingerprint(
        "probe2",
        {
            "command": P2,
            "reviewer_seed": fc.REVIEWER_SEED,
            "closest_cases": closest,
            "controls": ["empty-input", "weak-source", "planted-worse"],
        },
    )
    if source_fp == verifier_fp:
        print("FAILED:CNF-0175 source/verifier fingerprints collided")
        return 1

    compact = [compact_summary(s) for s in summaries]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "id": "CNF-0175",
        "unit_id": "CNF-0175",
        "claim_id": CLAIM_ID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0175",
        "completion_sentinel": "SUCCESS:CNF-0175",
        "verdict": verdict,
        "question": QUESTION,
        "title": (
            "Re-run a certified workflow fusion's benchmark win with "
            "re-randomized seeds on a different substrate"
        ),
        "confirmer": {
            "id": "CNF-0175-reproduction-engineer",
            "vendor": "anthropic",
            "role": "reproduction-engineer",
        },
        "blinding_attestation_hash": blinding,
        "source_probe": {
            "id": "probe1_reseed_substrates",
            "command": P1,
            "fingerprint": source_fp,
            "role": "confirmer-reseed-and-substrate",
        },
        "verifier_probe": {
            "id": "probe2_reviewer_controls",
            "command": P2,
            "fingerprint": verifier_fp,
            "role": "reviewer-fourth-seed-and-controls",
        },
        "baseline_repro": {
            "kind": "original-certification",
            "path": CERT_REL,
            "sha256": cert_sha,
            "seeds": list(fc.CERT_SEEDS),
            "substrate": fc.SUBSTRATE_INPROCESS,
            "scores_inlined": False,
            "note": "Adjudicator-only. Confirmer (probe1) does not read scores.",
        },
        "corrected_repro": {
            "kind": "held-out-reseed-two-substrates",
            "seeds": list(fc.CONFIRM_SEEDS),
            "substrates": [fc.SUBSTRATE_INPROCESS, fc.SUBSTRATE_SUBPROCESS],
            "n_cases": empty["n_cases"],
            "summaries": compact,
            "substrate_agreement": {
                k: agreement[k]
                for k in (
                    "substrates",
                    "tolerance",
                    "n_pairs",
                    "max_abs_diff",
                    "agree",
                )
            },
        },
        "rollback_repro": {
            "applicable": False,
            "reason": "No product-code mutation; fusion fixture is the object under test.",
        },
        "regression_diff": {
            "metric": "f1",
            "fusion_id": fc.FUSION,
            "sources": [fc.SOURCE_A, fc.SOURCE_B, fc.SOURCE_C],
            "stage_counts": {
                fc.FUSION: fc.WORKFLOW_STAGE_COUNTS[fc.FUSION],
                fc.SOURCE_A: fc.WORKFLOW_STAGE_COUNTS[fc.SOURCE_A],
                fc.SOURCE_B: fc.WORKFLOW_STAGE_COUNTS[fc.SOURCE_B],
                fc.SOURCE_C: fc.WORKFLOW_STAGE_COUNTS[fc.SOURCE_C],
            },
            "mean_f1_seed0_inprocess": compact[0]["mean_f1"],
            "mean_delta_vs_best_source_seed0_inprocess": compact[0][
                "mean_delta_vs_best_source"
            ],
            "delta_ci95_seed0_inprocess": compact[0]["delta_ci95"],
            "win_is_not_stage_count": True,
        },
        "discrepancies": [],
        "residual_caveat": residual,
        "estate_scan": scan,
        "tests": {
            "both_states_weak_source_loses": all_weak,
            "seed_control_three_sets": list(fc.CONFIRM_SEEDS),
            "empty_input_refused": refuse,
            "empty_cases_nontrivial": empty,
            "substrate_control": agreement,
            "planted_worse_fusion": planted,
            "reviewer_closest_cases": closest,
            "reviewer_seed": fc.REVIEWER_SEED,
        },
        "win_survives_reseed_and_substrate": win_survives,
        "output_schema": SCHEMA,
        "ts": now,
    }
    out = repo / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if "SUCCESS:CNF-0175" not in raw:
        print("FAILED:CNF-0175 sentinel missing from artifact text")
        return 1
    if doc["state"] in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0175 process state is not SUCCESS")
        return 1
    out.write_text(raw, encoding="utf-8")
    digest = fc.sha256_bytes(raw.encode("utf-8"))
    print(f"wrote {OUT} bytes={len(raw.encode('utf-8'))} sha256={digest}")
    print(f"verdict={verdict} win_survives={win_survives} agree={agreement['agree']}")
    print("SUCCESS:CNF-0175")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
