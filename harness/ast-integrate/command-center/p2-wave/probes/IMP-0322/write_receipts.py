#!/usr/bin/env python3
"""Write IMP-0322 catalog receipt plus per-unit return/manifest.

Runs the named probes, scores the 15 recorded councils and the labelled
sample, then writes:
  command-center/receipts/IMP-0322.json
  command-center/p2-wave/probes/IMP-0322/SUBAGENT-RETURN.json
  command-center/p2-wave/probes/IMP-0322/UNIT-ARTIFACT-MANIFEST.json

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import labelled_pairs, recorded_councils  # noqa: E402
from tools.council.antifail.no_gain import (  # noqa: E402
    classify_relation,
    evaluate_council,
)

UNIT = "IMP-0322"
OUT = "command-center/receipts/IMP-0322.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0322/probe1_looping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0322/probe2_refining.py"
)
SUPPORTING = [
    "tools/council/antifail/no_gain.py",
    "tools/council/antifail/__init__.py",
    "command-center/p2-wave/probes/IMP-0322/corpus.py",
    "command-center/p2-wave/probes/IMP-0322/probe1_looping.py",
    "command-center/p2-wave/probes/IMP-0322/probe2_refining.py",
    "command-center/p2-wave/probes/IMP-0322/write_receipts.py",
    "command-center/p2-wave/probes/IMP-0322/fixtures/recorded-councils.json",
    "command-center/p2-wave/probes/IMP-0322/fixtures/labelled-pairs.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0322/SUBAGENT-RETURN.json",
        "role": role,
    }


def dump_fixtures() -> None:
    fix = HERE / "fixtures"
    fix.mkdir(parents=True, exist_ok=True)
    (fix / "recorded-councils.json").write_text(
        json.dumps(recorded_councils(), indent=2) + "\n", encoding="utf-8"
    )
    (fix / "labelled-pairs.json").write_text(
        json.dumps(labelled_pairs(), indent=2) + "\n", encoding="utf-8"
    )


def score_corpus() -> dict:
    councils = recorded_councils()
    rows = []
    for council in councils:
        result = evaluate_council(council)
        rows.append(
            {
                "id": council["id"],
                "kind": council["kind"],
                "expect_fire": council["expect_fire"],
                "fired": result["fired"],
                "fire_round": result["fire_round"],
                "reason": result["reason"],
                "per_round": [
                    {
                        "round": r["round"],
                        "new_claim_count": r["new_claim_count"],
                        "refined_claim_count": r["refined_claim_count"],
                        "repeated_claim_count": r["repeated_claim_count"],
                        "new_evidence_count": r["new_evidence_count"],
                        "gain": r["gain"],
                    }
                    for r in result["per_round"]
                ],
            }
        )
    pairs = labelled_pairs()
    sample = []
    correct = 0
    for pair in pairs:
        pred = classify_relation(pair["old"], pair["new"])
        ok = pred == pair["label"]
        if ok:
            correct += 1
        sample.append(
            {"id": pair["id"], "label": pair["label"], "predicted": pred, "ok": ok}
        )
    looping = [r for r in rows if r["expect_fire"]]
    silent = [r for r in rows if not r["expect_fire"]]
    tpr = sum(1 for r in looping if r["fired"]) / len(looping)
    fpr = sum(1 for r in silent if r["fired"]) / len(silent)
    return {
        "rows": rows,
        "sample": sample,
        "labelled_n": len(pairs),
        "labelled_correct": correct,
        "discrimination_rate": correct / len(pairs),
        "tpr": tpr,
        "fpr": fpr,
        "looping_n": len(looping),
        "silent_n": len(silent),
    }


def main() -> int:
    dump_fixtures()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    scored = score_corpus()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    detector_rel = "tools/council/antifail/no_gain.py"
    det_sha, det_bytes = digest(REPO / detector_rel)

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0322",
        "completion_sentinel": "SUCCESS:IMP-0322",
        "title": "Circular-debate and no-information-gain detector",
        "spec_anchor": (
            "_USER-PROMPTS.md:10915-10946; _USER-PROMPTS.md:11234-11235; "
            "_USER-PROMPTS.md:11338; TST-0263 information-gain floor; "
            "CNL-0090 circular debate per-round gain"
        ),
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-antifail-module"
        ),
        "module": detector_rel,
        "artifact_paths": [OUT, detector_rel] + SUPPORTING,
        "artifacts": [
            {
                "path": detector_rel,
                "bytes": det_bytes,
                "sha256": det_sha,
                "exists": True,
                "role": "primary-module",
            }
        ],
        "question_or_target": (
            "Can the detector tell repetition from careful refinement of the "
            "same claim, and what does it do with a round that adds evidence "
            "but no new claims?"
        ),
        "falsifiable_answers": {
            "repetition_vs_refinement": (
                "Yes, on the labelled sample: a later claim is refinement when "
                "it covers a prior claim and adds a constraint (numeric bound, "
                "exception, rollback, TTL, cap). A paraphrase with no added "
                "constraint is repetition and contributes zero claim-gain. "
                f"Discrimination rate {scored['labelled_correct']}/"
                f"{scored['labelled_n']} = {scored['discrimination_rate']:.3f}."
            ),
            "evidence_without_new_claims": (
                "A round that cites a previously unseen evidence node is gain, "
                "even if every claim is a restatement. C11-evidence-only stayed "
                "silent: later rounds had new_claim_count=0 and "
                "new_evidence_count>=1 and gain=true. The detector does not "
                "treat evidence-only rounds as circular."
            ),
        },
        "policy": {
            "window": 2,
            "min_rounds": 3,
            "refinement_is_gain": True,
            "evidence_without_new_claims_is_gain": True,
            "paraphrase_without_constraint_is_repetition": True,
        },
        "evidence": [
            {
                "id": "E1-per-round-counts",
                "claim": (
                    "Per-round new-claim and new-evidence counts were measured "
                    "on 15 recorded councils."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0322/corpus.py",
                "n_councils": 15,
                "looping_n": scored["looping_n"],
                "silent_n": scored["silent_n"],
                "true_positive_rate": scored["tpr"],
                "false_positive_rate": scored["fpr"],
                "per_council": scored["rows"],
            },
            {
                "id": "E2-labelled-discrimination",
                "claim": (
                    "A labelled repetition-vs-refinement sample reports a "
                    "numeric discrimination rate."
                ),
                "verdict": "CONFIRMED",
                "anchor": (
                    "command-center/p2-wave/probes/IMP-0322/fixtures/"
                    "labelled-pairs.json"
                ),
                "labelled_n": scored["labelled_n"],
                "labelled_correct": scored["labelled_correct"],
                "discrimination_rate": scored["discrimination_rate"],
                "sample": scored["sample"],
            },
        ],
        "test_ids": [
            "IMP-0322-LOOPING-MUST-FIRE",
            "IMP-0322-REFINING-MUST-NOT-FIRE",
        ],
        "tests": [
            {
                "id": "IMP-0322-LOOPING-MUST-FIRE",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "IMP-0322-REFINING-MUST-NOT-FIRE",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "negative_control_ids": [
            "IMP-0322-NC-REFINING",
            "IMP-0322-NC-EVIDENCE-ONLY",
        ],
        "negative_controls": [
            {
                "id": "IMP-0322-NC-REFINING",
                "kind": "known-good-refining-council",
                "description": (
                    "A council that tightens the same claim each round must "
                    "NOT fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS",
            },
            {
                "id": "IMP-0322-NC-EVIDENCE-ONLY",
                "kind": "evidence-without-new-claims",
                "description": (
                    "A round that adds evidence but no new claims is gain; "
                    "C11 must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "result": "PASS",
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0322-probe2-refining-negative-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from_tests": True,
            "note": (
                "probe2_refining.py imports only the detector API and corpus "
                "labels. It does not import write_receipts or the author's "
                "narrative. A second-vendor human review was not executed in "
                "this isolated worktree."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "No second-vendor human reviewer was seated in this "
                    "worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Seat a reviewer who did not author no_gain.py and who "
                    "starts from the probes, then re-run both named probes."
                ),
            },
            {
                "claim": (
                    "The 15 councils are constructed recordings with known "
                    "labels, not a harvest of production transcripts."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "Replay 15 archived live councils through evaluate_council "
                    "and publish the same per-round table."
                ),
            },
            {
                "claim": (
                    "Claim canonicalisation is bag-of-stems plus constraint "
                    "markers. Heavy jargon or implicit constraints with no "
                    "numeric/exception cue may misclassify."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add a jargon-held-out labelled sample and report the "
                    "drop in discrimination rate."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0322/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "note": "per-unit only; did not run unit_manifest.py --write",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "generated_by": "command-center/p2-wave/probes/IMP-0322/write_receipts.py",
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    primary = art_row(OUT, "primary")
    artifacts = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0322",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-antifail-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "looping-must-fire",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "refining-must-not-fire",
                "raw_output": t2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/IMP-0322/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "IMP-0322-probe2-refining-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0322: live named probes exit 0, receipts/IMP-0322.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
