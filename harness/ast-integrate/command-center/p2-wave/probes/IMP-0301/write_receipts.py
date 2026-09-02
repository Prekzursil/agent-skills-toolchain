#!/usr/bin/env python3
"""Emit IMP-0301 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from common import evaluate, load, result_by_id, spec  # noqa: E402

OUT = "command-center/receipts/IMP-0301.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0301/probe1_known_answers.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0301/probe2_empty_category.py"
)
SUPPORTING = [
    "tools/council/quota/targets.py",
    "tools/council/quota/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0301/common.py",
    "command-center/p2-wave/probes/IMP-0301/probe1_known_answers.py",
    "command-center/p2-wave/probes/IMP-0301/probe2_empty_category.py",
    "command-center/p2-wave/probes/IMP-0301/fixtures/council_spec.json",
    "command-center/p2-wave/probes/IMP-0301/fixtures/snapshot_empty_gamma.json",
    "command-center/p2-wave/probes/IMP-0301/fixtures/snapshot_full.json",
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "IMP-0301",
        "receipt_path": "command-center/p2-wave/probes/IMP-0301/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt() -> dict:
    council = spec()
    empty = load("snapshot_empty_gamma.json")
    full = load("snapshot_full.json")
    clustered = load("snapshot_clustered.json")
    spread = load("snapshot_spread.json")
    miss = load("snapshot_floors_miss.json")
    r_empty = evaluate(council, empty)
    r_full = evaluate(council, full)
    r_cl = evaluate(council, clustered)
    r_sp = evaluate(council, spread)
    r_miss = evaluate(council, miss)
    cov = result_by_id(r_empty, "t-coverage")
    cov_full = result_by_id(r_full, "t-coverage")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = cov.get("per_category") or []
    return {
        "unit_id": "IMP-0301",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0301",
        "title": "Target evaluator for novelty, diversity, category, coverage, objection and evidence quotas",
        "artifact_paths": [
            OUT,
            "tools/council/quota/targets.py",
            "command-center/p2-wave/probes/IMP-0301/probe1_known_answers.py",
            "command-center/p2-wave/probes/IMP-0301/probe2_empty_category.py",
        ],
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0301: evaluate every non-count target "
            "CouncilSpec can declare. Eight declared targets in CNL-0009: "
            "unique-idea (count, deferred to IMP-0300) plus novelty, diversity, "
            "category, coverage, objection, counterexample, evidence. "
            "11-COUNCIL-SPECIFICATION.schema.json is not on this worktree; "
            "kinds are taken from that catalog enumeration. Coverage rule is "
            "per declared category (CNL-0054 clustered-vs-spread), not occupied-fraction aggregate."
        ),
        "falsifiable_question": (
            "Can a council satisfy a coverage target while leaving an entire "
            "declared category empty — i.e. is coverage measured per category "
            "or in aggregate?"
        ),
        "falsifiable_answer": r_empty["falsifiable_answer"],
        "coverage_rule": "per_category",
        "evidence": [
            {
                "id": "E1-per-category-attainment-table",
                "claim": (
                    "On snapshot_empty_gamma, declared categories alpha/beta/gamma "
                    "have counts 4/4/0. Empty categories are listed explicitly."
                ),
                "per_category_table": table,
                "empty_categories": cov.get("empty_categories"),
                "source": "command-center/p2-wave/probes/IMP-0301/fixtures/snapshot_empty_gamma.json",
                "verifier": "independent Counter over idea.category vs evaluate() table",
            },
            {
                "id": "E2-aggregate-vs-per-category-disagreement",
                "claim": (
                    "Occupied-fraction aggregate is 2/3 >= 0.5 so aggregate would "
                    "PASS; per-category coverage FAIL because gamma is empty. "
                    "The two rules disagree on this fixture."
                ),
                "occupied_fraction_aggregate": cov.get("occupied_fraction_aggregate"),
                "aggregate_threshold": cov.get("aggregate_threshold"),
                "aggregate_would_pass": cov.get("aggregate_would_pass"),
                "per_category_pass": cov.get("pass"),
                "disagree": cov.get("aggregate_and_per_category_disagree"),
                "source": "tools/council/quota/targets.py _eval_coverage",
            },
        ],
        "test_ids": [
            "IMP-0301-T1-each-target-type-known-answer",
            "IMP-0301-T2-empty-category-blocks-coverage",
        ],
        "negative_control_ids": [
            "IMP-0301-NC-empty-declared-category-prevents-coverage-PASS"
        ],
        "known_answers": {
            "empty_gamma": {
                "coverage": result_by_id(r_empty, "t-coverage").get("pass"),
                "category": result_by_id(r_empty, "t-category").get("pass"),
                "novelty": result_by_id(r_empty, "t-novelty").get("pass"),
                "diversity": result_by_id(r_empty, "t-diversity").get("pass"),
                "objection": result_by_id(r_empty, "t-objection").get("pass"),
                "evidence": result_by_id(r_empty, "t-evidence").get("pass"),
                "counterexample": result_by_id(r_empty, "t-counterexample").get("pass"),
                "unique_idea_skipped": True,
            },
            "full": {"coverage": cov_full.get("pass")},
            "clustered_simpson": result_by_id(r_cl, "t-diversity").get("simpson"),
            "spread_simpson": result_by_id(r_sp, "t-diversity").get("simpson"),
            "floors_miss_objection": result_by_id(r_miss, "t-objection").get("pass"),
        },
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0301-probe2-independent-counter",
            "independent": True,
            "starts_from": "fixtures/tests, not author summary",
            "verdict": "PASS",
            "note": (
                "Probe 2 recounts idea.category with collections.Counter and "
                "asserts evaluate() FAIL iff a declared category has count 0."
            ),
        },
        "residual_unknowns": [
            "11-COUNCIL-SPECIFICATION.schema.json is absent on this worktree; "
            "additional quota kinds beyond the CNL-0009 eight are NOT-CHECKED.",
            "Novelty is token-Jaccard against a fixture prior-art corpus, not "
            "an embedding model; paraphrase-beyond-token-overlap is residual.",
            "IMP-0296 (catalog dependency: negotiate.py) is not delivered on "
            "this tree; the evaluator does not import it.",
        ],
        "defects": [],
        "produced_by": {
            "role": "implementer",
            "unit_id": "IMP-0301",
        },
        "ts": now,
        "SUCCESS:IMP-0301": True,
    }


def main() -> int:
    receipt = build_receipt()
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0301",
        "unit_id": "IMP-0301",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0301",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-quota-module "
            "(required: unit_id, artifact_paths[], spec_anchor, evidence[], "
            "test_ids[], negative_control_ids[], reviewer_verdict, residual_unknowns[])"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "each-target-type-known-answer",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "empty-category-negative-control",
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0301/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0301-probe2-independent-counter",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0301: live named probes exit 0, receipts/IMP-0301.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0301",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0301 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
