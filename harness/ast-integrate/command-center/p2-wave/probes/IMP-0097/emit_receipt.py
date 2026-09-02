#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0097.json from live score arithmetic."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.marketplace.benchmark_gaming import (  # noqa: E402
    FLAG_SELF_AUTHORED,
    contribution,
    score_with_benchmarks,
    score_without_record,
)
from tools.marketplace.scenario import load_scenario  # noqa: E402
from tools.marketplace.tests.test_benchmark_gaming import run_all  # noqa: E402

OUT = REPO / "command-center" / "receipts" / "IMP-0097.json"


def generating_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable: git rev-parse failed"
    if proc.returncode != 0:
        return "unavailable: worktree is not a git repository"
    return proc.stdout.strip() or "unavailable: empty HEAD"


def live_evidence() -> dict:
    measurements, records, provenance, raw = load_scenario()
    full = score_with_benchmarks(measurements, records, provenance)
    by_id = {r.record_id: r for r in records}
    dead_ids = [
        "rec.unreproduced.claim",
        "rec.publisher-only.rerun",
        "rec.failed.independent",
    ]
    equalities = []
    for dead_id in dead_ids:
        dead = by_id[dead_id]
        without = score_without_record(measurements, records, provenance, dead_id)
        equalities.append(
            {
                "record_id": dead_id,
                "claimed_delta": dead.claimed_delta,
                "contribution": contribution(dead, provenance),
                "full_total": full.total,
                "without_total": without.total,
                "equal": full.total == without.total,
            }
        )
    good = by_id["rec.independent.reproduced"]
    planted = by_id["rec.self-authored.reproduced"]
    without_good = score_without_record(
        measurements, records, provenance, good.record_id
    )
    without_planted = score_without_record(
        measurements, records, provenance, planted.record_id
    )
    flags = [f for f in full.flags if f["flag"] == FLAG_SELF_AUTHORED]
    return {
        "package_id": raw["package_id"],
        "package_version": raw["package_version"],
        "publisher_id": raw["publisher_id"],
        "base": full.base,
        "total": full.total,
        "component_breakdown": full.component_breakdown,
        "record_rows": list(full.records),
        "flags": list(full.flags),
        "signal_1_unreproduced_zero": {
            "full_total": full.total,
            "unreproduced_contribution": 0.0,
            "unreproduced_claimed_delta": by_id["rec.unreproduced.claim"].claimed_delta,
            "equalities": equalities,
            "all_equal": all(row["equal"] and row["contribution"] == 0.0 for row in equalities),
        },
        "signal_2_self_authored": {
            "flagged_record_id": planted.record_id,
            "case_set_id": planted.case_set_id,
            "authors": list(provenance[planted.case_set_id].authors),
            "flag": FLAG_SELF_AUTHORED,
            "flag_count": len(flags),
            "contribution": contribution(planted, provenance),
            "score_unchanged_when_removed": full.total == without_planted.total,
        },
        "negative_control": {
            "record_id": good.record_id,
            "case_set_id": good.case_set_id,
            "full_total": full.total,
            "without_good": without_good.total,
            "raised_by": full.total - without_good.total,
            "claimed_delta": good.claimed_delta,
        },
    }


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    import hashlib

    return {
        "path": rel,
        "role": role,
        "exists": True,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    tests_rc = run_all()
    if tests_rc != 0:
        print("FAILED:IMP-0097 tests")
        return tests_rc
    evidence = live_evidence()
    if not evidence["signal_1_unreproduced_zero"]["all_equal"]:
        print("FAILED:IMP-0097 signal 1 equality")
        return 1
    if evidence["signal_2_self_authored"]["contribution"] != 0.0:
        print("FAILED:IMP-0097 signal 2 still contributes")
        return 1
    if evidence["negative_control"]["raised_by"] <= 0:
        print("FAILED:IMP-0097 negative control did not raise")
        return 1

    supporting = [
        "tools/marketplace/benchmark_gaming.py",
        "tools/marketplace/quality_score.py",
        "tools/marketplace/benchmark_evidence.py",
        "tools/marketplace/case_provenance.py",
        "tools/marketplace/scenario.py",
        "tools/marketplace/tests/test_benchmark_gaming.py",
        "tools/marketplace/fixtures/case_sets/known_provenance.json",
        "tools/marketplace/fixtures/packages/imp0097_scenario.json",
        "command-center/p2-wave/probes/IMP-0097/probe1_unreproduced_zero.py",
        "command-center/p2-wave/probes/IMP-0097/probe2_self_authored_case_set.py",
    ]
    artifacts = [artifact_row(rel, "supporting") for rel in supporting]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": "IMP-0097",
        "unit_id": "IMP-0097",
        "title": "Benchmark-gaming defence: unreproducible evidence scores zero",
        "completion_sentinel": "SUCCESS:IMP-0097",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "output_path": "command-center/receipts/IMP-0097.json",
        "output_schema": "command-center/schema/receipt.schema.json",
        "generated_at": now,
        "generating_commit": generating_commit(),
        "question_or_target": (
            "A benchmark claim contributes to the quality score only when its "
            "reproduction has been independently executed at least once and "
            "landed within tolerance; records that fail or cannot be re-run "
            "are retained as UNREPRODUCED and contribute nothing. Self-selected "
            "case sets the package authored alone are flagged and also add zero."
        ),
        "evidence": evidence,
        "evidence_anchors": [
            {
                "id": "signal-1-unreproduced-zero",
                "path": "tools/marketplace/benchmark_gaming.py",
                "symbol": "contribution / score_without_record",
                "observation": evidence["signal_1_unreproduced_zero"],
            },
            {
                "id": "signal-2-self-authored-case-set",
                "path": "tools/marketplace/fixtures/case_sets/known_provenance.json",
                "symbol": "bench.acme.easy-v1 authors",
                "observation": evidence["signal_2_self_authored"],
            },
            {
                "id": "negative-control-independent-raises",
                "path": "tools/marketplace/tests/test_benchmark_gaming.py",
                "symbol": "test_unreproduced_contributes_zero",
                "observation": evidence["negative_control"],
            },
        ],
        "tests": [
            {
                "id": "tools/marketplace/tests/test_benchmark_gaming.py::test_unreproduced_contributes_zero",
                "result": "PASS",
            },
            {
                "id": "tools/marketplace/tests/test_benchmark_gaming.py::test_self_authored_case_set_is_flagged",
                "result": "PASS",
            },
            {
                "id": "NEGATIVE CONTROL: reproduced independently-cased benchmark raises score in the same run",
                "result": "PASS",
                "raised_by": evidence["negative_control"]["raised_by"],
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0097-adversarial-residual",
            "independent": True,
            "verdict": "PASS",
            "disclosed_residual": (
                "Sock-puppet authorship and captured independence still survive. "
                "Self-authorship is identifier equality against "
                "CaseSetProvenance.authors; a publisher who registers a case set "
                "under a distinct author_id they control, or who adds a "
                "rubber-stamp co-author_id, is not flagged. Independent "
                "reproduction is executor_id != publisher_id plus a metric inside "
                "tolerance; a publisher-controlled lab under another executor_id "
                "on publisher hardware still counts. The defence has no "
                "organizational-identity graph and does not require a distinct "
                "environment class from the original claim."
            ),
        },
        "artifacts": artifacts,
        "notes": (
            "IMP-0094/IMP-0096 are not claimed delivered. Base score here is the "
            "local decomposable component sum IMP-0097 needs so the gaming filter "
            "can be proven in arithmetic. Did not run unit_manifest.py --write."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(receipt, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT.relative_to(REPO).as_posix()} bytes={OUT.stat().st_size}")
    print("SUCCESS:IMP-0097")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
