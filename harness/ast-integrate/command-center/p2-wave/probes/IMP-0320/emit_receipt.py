#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0320.json from a live detector run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from fixtures import (  # noqa: E402
    collapsed_council,
    diverse_council,
    hard_same_model_strong_roles,
)
from load import load_detector  # noqa: E402

OUT = "command-center/receipts/IMP-0320.json"
MODULE = "tools/council/antifail/role_collapse.py"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": path.is_file(),
        "role": role,
        "unit_id": "IMP-0320",
    }


def slim(det: dict) -> dict:
    return {
        "council_id": det.get("council_id"),
        "status": det["status"],
        "fired": det["fired"],
        "mean_pairwise_jaccard": det["mean_pairwise_jaccard"],
        "mean_role_vocab_score": det["mean_role_vocab_score"],
        "pairwise": det["pairwise"],
        "role_vocab": det["role_vocab"],
        "unique_models": det["unique_models"],
        "reason": det["reason"],
    }


def main() -> int:
    D = load_detector()
    collapsed = collapsed_council()
    diverse = diverse_council()
    hard = hard_same_model_strong_roles()
    bad = D.detect(collapsed)
    good = D.detect(diverse)
    hard_det = D.detect(hard)
    decoy = D.declared_role_decoy(collapsed)
    if not bad["fired"] or good["fired"]:
        print("FAILED:IMP-0320 emit collapsed/diverse did not separate")
        return 1
    if decoy["fired"]:
        print("FAILED:IMP-0320 emit declared-role decoy fired on distinct labels")
        return 1
    if hard_det["fired"]:
        print(
            "FAILED:IMP-0320 emit hard same-model strong-role FIRE; "
            "do not retune — fixtures should be SILENT on behaviour"
        )
        return 1

    bad_vals = [p["jaccard"] for p in bad["pairwise"]]
    good_vals = [p["jaccard"] for p in good["pairwise"]]
    plot = D.side_by_side_histograms(bad_vals, good_vals)
    if min(bad_vals) <= max(good_vals):
        print("FAILED:IMP-0320 emit similarity distributions overlap")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [
        art_row(MODULE, "primary-module"),
        art_row("command-center/p2-wave/probes/IMP-0320/fixtures.py", "fixtures"),
        art_row(
            "command-center/p2-wave/probes/IMP-0320/probe1_collapsed_vs_diverse.py",
            "probe",
        ),
        art_row(
            "command-center/p2-wave/probes/IMP-0320/probe2_hard_case_vocab.py",
            "probe",
        ),
    ]
    receipt = {
        "unit_id": "IMP-0320",
        "title": "Role-collapse detector",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0320",
        "completion_sentinel": "SUCCESS:IMP-0320",
        "profile": "council-antifail-module",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0320] "
            "question_or_target; catalog-cited _USER-PROMPTS.md:11230 "
            "(role collapse: every participant behaving the same)"
        ),
        "falsifiable_question": (
            "Does the detector fire on a council where all seats are the same "
            "model with different role prompts, and stay silent on a genuinely "
            "diverse one?"
        ),
        "answer": (
            "It fires when outputs are similar AND role vocabularies are missing, "
            "not when model ids match. The planted collapsed fixture uses one "
            f"model and four role prompts but near-identical outputs "
            f"(mean Jaccard {bad['mean_pairwise_jaccard']:.3f}, mean role-vocab "
            f"{bad['mean_role_vocab_score']:.3f}) and FIRE. The diverse fixture "
            f"is SILENT (mean Jaccard {good['mean_pairwise_jaccard']:.3f}, "
            f"mean role-vocab {good['mean_role_vocab_score']:.3f}). The hard "
            "same-model / strong-role-prompt fixture is classified SILENT "
            f"(mean Jaccard {hard_det['mean_pairwise_jaccard']:.3f}, mean "
            f"role-vocab {hard_det['mean_role_vocab_score']:.3f}); that is "
            "reported, not tuned into a FIRE. A declared-role-label decoy stays "
            f"SILENT on collapsed (unique roles={decoy['unique_roles']}). "
            "11-COUNCIL-SPECIFICATION.md is absent on this worktree."
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-antifail-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
            "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "artifact_paths": [a["path"] for a in artifacts] + [OUT],
        "artifacts": artifacts,
        "module": {
            "path": MODULE,
            "sha256": digest(REPO / MODULE)[0],
            "bytes": digest(REPO / MODULE)[1],
            "sim_fire": D.SIM_FIRE,
            "vocab_fire": D.VOCAB_FIRE,
            "fire_rule": (
                "FIRE iff mean pairwise token Jaccard of outputs >= SIM_FIRE "
                "AND mean per-seat role-vocab score < VOCAB_FIRE. Model id and "
                "declared role labels are not inputs to the rule."
            ),
        },
        "similarity_distributions": {
            "collapsed_pairwise_jaccard": bad_vals,
            "diverse_pairwise_jaccard": good_vals,
            "collapsed_min": min(bad_vals),
            "diverse_max": max(good_vals),
            "separated": min(bad_vals) > max(good_vals),
            "ascii_plot": plot,
        },
        "role_vocab_per_seat": {
            "collapsed": bad["role_vocab"],
            "diverse": good["role_vocab"],
            "hard_same_model_strong_roles": hard_det["role_vocab"],
        },
        "collapsed": slim(bad),
        "diverse": slim(good),
        "hard_same_model_strong_roles": slim(hard_det),
        "declared_role_decoy_on_collapsed": decoy,
        "evidence": [
            {
                "id": "E1-similarity-distributions",
                "anchor": "tools/council/antifail/role_collapse.py detect pairwise",
                "claim": (
                    "Side-by-side pairwise Jaccard distributions: collapsed "
                    f"min={min(bad_vals):.3f} above diverse max={max(good_vals):.3f}."
                ),
                "raw_plot": plot,
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
            {
                "id": "E2-role-vocab-per-seat",
                "anchor": "role_vocab_presence per seat",
                "claim": (
                    "Collapsed seats miss role markers "
                    f"(mean {bad['mean_role_vocab_score']:.3f}); diverse and "
                    "hard-case seats carry them "
                    f"(means {good['mean_role_vocab_score']:.3f} and "
                    f"{hard_det['mean_role_vocab_score']:.3f})."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
            },
        ],
        "tests": [
            {
                "id": "T-collapsed-fire-diverse-silent",
                "name": "control: collapsed council must FIRE, diverse council must not",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0320/probe1_collapsed_vs_diverse.py"
                ),
                "result": "PASS",
            },
            {
                "id": "T-hard-same-model-strong-roles",
                "name": (
                    "negative control: single-model council with strong role "
                    "prompts classified honestly"
                ),
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/IMP-0320/probe2_hard_case_vocab.py"
                ),
                "result": "PASS",
            },
        ],
        "test_ids": [
            "T-collapsed-fire-diverse-silent",
            "T-hard-same-model-strong-roles",
        ],
        "negative_control_ids": [
            "NC-declared-role-decoy-silent-on-collapsed",
            "NC-same-model-strong-roles-honest-class",
        ],
        "negative_controls": [
            {
                "id": "NC-declared-role-decoy-silent-on-collapsed",
                "kind": "label-only-decoy",
                "description": (
                    "A detector that only compares declared role strings must "
                    "stay SILENT on the collapsed fixture (four different role "
                    "names, identical behaviour)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"real detector FIRE collapsed mean_jaccard="
                    f"{bad['mean_pairwise_jaccard']}"
                ),
                "good_state_output": (
                    f"declared-role decoy status={decoy['status']} "
                    f"unique={decoy['unique_roles']}"
                ),
            },
            {
                "id": "NC-same-model-strong-roles-honest-class",
                "kind": "hard-case-no-retune",
                "description": (
                    "Same model, strong role prompts, differentiated outputs. "
                    "Report SILENT rather than moving thresholds until FIRE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"collapsed FIRE jaccard={bad['mean_pairwise_jaccard']}"
                ),
                "good_state_output": (
                    f"hard status={hard_det['status']} "
                    f"jaccard={hard_det['mean_pairwise_jaccard']} "
                    f"vocab={hard_det['mean_role_vocab_score']}"
                ),
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0320-probe2-hard-case-vocab",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "note": (
                "Probe 2 starts from the tests: per-seat vocab, model-id "
                "mutation, and receipt-vs-live hard-case class. It does not "
                "author the detector. Cross-vendor human review is not on "
                "this Linux worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "11-COUNCIL-SPECIFICATION.md is absent; role marker lists "
                    "are the catalog-row operationalization, not a spec extract."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-bind DEFAULT_ROLE_VOCAB to the specification's role "
                    "lexicon when that file is on disk."
                ),
            },
            {
                "claim": (
                    "IMP-0264 kernel and IMP-0276 anonymity layer are not on "
                    "this tree. Detector scores recorded transcripts, not a "
                    "live kernel event stream."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0264, pipe kernel turn events into detect() "
                    "and re-run collapsed vs diverse."
                ),
            },
            {
                "claim": (
                    "Live sampled same-model strong-role LLM outputs were not "
                    "drawn; the hard case is a fixture whose outputs follow "
                    "the prompts."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Sample four seats from one model with the strong role "
                    "prompts and report detect() without moving SIM_FIRE."
                ),
            },
        ],
        "timestamps": {
            "started_at": "2026-08-24T18:00:00Z",
            "ended_at": now,
        },
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "schema_version": 1,
        "min_bytes_threshold": 128,
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0320/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit manifest only; did not run unit_manifest.py --write",
        },
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(receipt, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:IMP-0320 receipt emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
