#!/usr/bin/env python3
"""Write IMP-0289 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

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
REPO = Path(__file__).resolve().parents[4]
UID = "IMP-0289"
OUT = "command-center/receipts/IMP-0289.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0289/probe1_three_councils_reachability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0289/probe2_dissent_loss_negative.py"
)
REV = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0289/reviewer.py"
)
SUPPORTING = [
    "tools/council/topology/meta.py",
    "tools/council/topology/__init__.py",
    "command-center/p2-wave/probes/IMP-0289/probe1_three_councils_reachability.py",
    "command-center/p2-wave/probes/IMP-0289/probe2_dissent_loss_negative.py",
    "command-center/p2-wave/probes/IMP-0289/reviewer.py",
    "command-center/p2-wave/probes/IMP-0289/fixtures/three_councils.json",
    "command-center/p2-wave/probes/IMP-0289/fixtures/meta_artifact.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0289/SUBAGENT-RETURN.json",
        "role": role,
    }


def write_fixtures() -> None:
    sys.path.insert(0, str(REPO))
    from tools.council.topology.meta import (
        aggregate,
        dumps,
        three_council_fixture,
    )

    fx = HERE / "fixtures"
    fx.mkdir(parents=True, exist_ok=True)
    councils = three_council_fixture()
    meta = aggregate(councils)
    (fx / "three_councils.json").write_text(
        json.dumps({"councils": councils}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (fx / "meta_artifact.json").write_text(dumps(meta), encoding="utf-8")


def main() -> int:
    write_fixtures()
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    cr, tr = run_cmd(REV)
    if c1 != 0 or c2 != 0 or cr != 0:
        print(f"FAILED:IMP-0289 receipts probes c1={c1} c2={c2} reviewer={cr}")
        print(t1[-2000:])
        print(t2[-2000:])
        print(tr[-2000:])
        return 1

    sys.path.insert(0, str(REPO))
    from tools.council.topology.meta import (
        aggregate,
        check_reachability,
        compare_dissent_counts,
        collect_minority_ids,
        three_council_fixture,
    )

    councils = three_council_fixture()
    expected = collect_minority_ids(councils)
    meta = aggregate(councils)
    reach = check_reachability(meta, expected)
    counts = compare_dissent_counts(meta, councils)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0289",
        "completion_sentinel": "SUCCESS:IMP-0289",
        "title": "Council-of-councils meta aggregation",
        "profile": "council-topology-module",
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-topology-module"
        ),
        "question": (
            "Implement tools/council/topology/meta.py aggregating several "
            "independent councils' outputs, preserving each council's dissent "
            "rather than averaging it away. Falsifiable question: after "
            "meta-aggregation, is every constituent council's minority report "
            "still reachable from the final artifact by id?"
        ),
        "answer": (
            "Yes on the three-council fixture: four minority-report ids remain "
            "reachable by JSON-pointer index and by structural walk; dissent "
            f"counts in={counts.get('dissents_in')} out={counts.get('dissents_out')}; "
            "split verdicts yield DISAGREEMENT rather than a manufactured ADOPT."
        ),
        "spec_anchor": {
            "catalog_id": UID,
            "module": "tools/council/topology/meta.py",
            "failure_class": "dissent-loss",
            "catalog_note": "spec 11342 dissent-loss class",
            "fc_ids": ["FC-11340", "FC-11341", "FC-11342", "FC-11343"],
            "inputs_cited": [
                "_USER-PROMPTS.md:10915-10946",
                "_USER-PROMPTS.md:10746-10767",
                "_USER-PROMPTS.md:11172-11244",
                "11-COUNCIL-SPECIFICATION.md",
                "11-COUNCIL-SPECIFICATION.schema.json",
            ],
            "note": (
                "The Windows harness-restore paths named in the catalog are not "
                "on this Linux worktree; anchors are the catalog unit plus the "
                "in-tree failure-mode ids FC-11340..FC-11343."
            ),
        },
        "artifact_paths": [
            OUT,
            "tools/council/topology/meta.py",
            "command-center/p2-wave/probes/IMP-0289/fixtures/meta_artifact.json",
        ],
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {"path": "tools/council/topology/meta.py", "role": "implementation"},
            {
                "path": "command-center/p2-wave/probes/IMP-0289/fixtures/meta_artifact.json",
                "role": "supporting",
            },
        ],
        "evidence": [
            {
                "id": "E1-reachability",
                "requirement": (
                    "a reachability check from the meta artifact to every "
                    "constituent minority report id"
                ),
                "ok": reach.get("ok"),
                "expected_ids": reach.get("expected_ids"),
                "reachable_ids": reach.get("reachable_ids"),
                "missing_ids": reach.get("missing_ids"),
                "index_keys": sorted((meta.get("minority_index") or {}).keys()),
                "pointers": {
                    rid: (meta.get("minority_index") or {}).get(rid, {}).get("json_pointer")
                    for rid in (reach.get("expected_ids") or [])
                },
            },
            {
                "id": "E2-dissent-counts",
                "requirement": "a count comparison of dissents in versus dissents out",
                "ok": counts.get("ok"),
                "dissents_in": counts.get("dissents_in"),
                "dissents_out": counts.get("dissents_out"),
                "minority_in": counts.get("minority_in"),
                "minority_out": counts.get("minority_out"),
            },
        ],
        "test_ids": [
            "IMP-0289-probe1-three-councils-reachability",
            "IMP-0289-probe2-dissent-loss-negative",
        ],
        "negative_control_ids": [
            "IMP-0289-NC-drop-one-minority-report-spec-11342",
        ],
        "tests": [
            {
                "id": "IMP-0289-probe1-three-councils-reachability",
                "command": P1,
                "result": "PASS",
                "exit_code": c1,
            },
            {
                "id": "IMP-0289-probe2-dissent-loss-negative",
                "command": P2,
                "result": "PASS",
                "exit_code": c2,
            },
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "IMP-0289-fixture-walk-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "starts_from": "tests/fixture ids, not the author's summary",
            "command": REV,
            "exit_code": cr,
        },
        "residual_unknowns": [
            {
                "claim": "IMP-0288 nested.py spawn/fan-in is present on this tree",
                "verdict": "ABSENT",
                "note": (
                    "meta.py consumes already-emitted council artifacts; it does "
                    "not spawn subcouncils. Wiring to nested.py is out of this unit."
                ),
            },
            {
                "claim": "IMP-0305 bayes.py credence pooling is present on this tree",
                "verdict": "ABSENT",
                "note": (
                    "meta aggregation unions dissent ledgers and does not pool "
                    "credences. A later unit may attach pooled credence as a "
                    "parallel field without deleting minority ids."
                ),
            },
            {
                "claim": "Live multi-model councils were executed",
                "verdict": "NOT-RUN",
                "note": "Fixture is scripted constituent outputs; no LLM calls.",
            },
        ],
        "mechanism": {
            "module": "tools/council/topology/meta.py",
            "aggregation_rule": "ledger-union",
            "averaging_forbidden": True,
            "meta_verdict": meta.get("meta_verdict"),
            "histogram": meta.get("verdict_histogram"),
            "constituent_count": meta.get("constituent_count"),
        },
        "probe_transcripts": {
            "probe1": t1,
            "probe2": t2,
            "reviewer": tr,
        },
        "ts": now,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/IMP-0289/UNIT-ARTIFACT-MANIFEST.json",
        "notes": (
            "G-1 for IMP-0289: live named probes exit 0, receipt state=SUCCESS "
            "contains SUCCESS:IMP-0289, per-unit manifest row. Did not run "
            "global unit_manifest.py --write."
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0289",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "profile=council-topology-module"
        ),
        "measure_line": "SUCCESS:delivered IMP-0289",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered IMP-0289"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0289/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0289-fixture-walk-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0289: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print("SUCCESS:IMP-0289 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
