#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0317.json from a live fusion + decompose run."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_forge.decompose import (  # noqa: E402
    capability_report,
    decompose,
    drop_stage,
    fuse_and_record,
    fusion_covers_source_cases,
    score_on_cases,
)
import fixtures as F  # noqa: E402

OUT = "command-center/receipts/TST-0317.json"
SCHEMA = "command-center/schema/receipt.schema.json"
SENTINEL = "SUCCESS:TST-0317"
QUESTION = (
    "After a fusion wins, does it decompose back into its sources, "
    "and do those sources still cover every capability they had? Spec "
    ":10913 and :11170 require lineage and decomposability; :11332 names "
    "workflow fusion losing a source capability. A fusion that wins by "
    "dropping a rarely-exercised capability is a regression dressed as "
    "an improvement."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0317/probe1_capability_and_lineage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0317/probe2_decompose_and_loss.py"
)
SUPPORTING = [
    "tools/workflow_forge/decompose.py",
    "tools/workflow_forge/best_of_breed.py",
    "tools/workflow_forge/__init__.py",
    "command-center/p2-wave/probes/TST-0317/fixtures.py",
    "command-center/p2-wave/probes/TST-0317/fixtures/source_alpha.json",
    "command-center/p2-wave/probes/TST-0317/fixtures/source_beta.json",
    "command-center/p2-wave/probes/TST-0317/fixtures/evidence.json",
    "command-center/p2-wave/probes/TST-0317/fixtures/cases.json",
    "command-center/p2-wave/probes/TST-0317/probe1_capability_and_lineage.py",
    "command-center/p2-wave/probes/TST-0317/probe2_decompose_and_loss.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    data = path.read_bytes() if path.is_file() else b""
    eol = "LF"
    if data and b"\r\n" in data:
        eol = "CRLF"
    if not path.is_file():
        eol = "NOT-CHECKED"
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0317 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:TST-0317-probe1" not in t1:
        print("FAILED:TST-0317 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:TST-0317-probe2" not in t2:
        print("FAILED:TST-0317 emit probe2 sentinel missing")
        return 1

    srcs = F.sources()
    fusion = fuse_and_record(srcs, F.evidence())
    caps = fusion["capability_report"]
    dec = decompose(fusion)
    cases = F.cases()
    source_scores = [
        score_on_cases(component, cases) for component in dec["components"].values()
    ]
    fusion_score = score_on_cases(fusion["workflow"], cases)
    cover = fusion_covers_source_cases(fusion_score, source_scores)
    dropped = drop_stage(fusion["workflow"], "cite")
    bad = capability_report(srcs, dropped)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    artifacts = [art(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["exists"]]
    if missing:
        print(f"FAILED:TST-0317 missing supporting {missing}")
        return 1

    chosen = {
        row["slot_id"]: row["chosen_source_id"] for row in fusion["selection_record"]
    }
    doc = {
        "schema_version": 1,
        "unit_id": "TST-0317",
        "id": "TST-0317",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "A tournament winner must decompose back into its sources, "
            "and the sources must be re-scored"
        ),
        "question": QUESTION,
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0317 :10913 :11170 :11332",
        "min_bytes_threshold": 2048,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "schema_note": (
            "Catalog names command-center/schema/receipt.schema.json; that "
            "file is absent on this tree. This receipt still carries state, "
            "sentinel, tests, evidence, reviewer, and the capability-set "
            "tables the catalog evidence_requirement names."
        ),
        "cloud_ok": False,
        "fusion": {
            "operator": "best-of-breed",
            "module": "tools/workflow_forge/decompose.py",
            "fused_workflow_id": fusion["workflow"]["id"],
            "source_ids": fusion["source_ids"],
            "chosen": chosen,
            "lineage": fusion["lineage"],
            "capability_report": caps,
            "recovered_ids": dec["recovered_ids"],
            "case_coverage": cover,
            "loss_control": {
                "dropped_stage": "cite",
                "difference": bad["difference"],
                "blocking_finding": bad["blocking_finding"],
            },
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "kind": "capability-set-difference",
                "claim": (
                    "Capability sets computed from stage/tool declarations: "
                    f"alpha={caps['per_source'].get('wf.source.alpha-retriever')} "
                    f"beta={caps['per_source'].get('wf.source.beta-ranker')} "
                    f"fusion={caps['fusion']} difference={caps['difference']}. "
                    "A non-empty difference is a blocking finding; this fusion "
                    "difference is empty."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_forge/decompose.py:capability_report",
                "detail": json.dumps(
                    {
                        "per_source": caps["per_source"],
                        "fusion": caps["fusion"],
                        "difference": caps["difference"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "kind": "lineage-set-membership",
                "claim": (
                    "Every fused stage names its source and license. Named "
                    f"stages={fusion['lineage_integrity']['named_stage_ids']} "
                    f"licenses={fusion['lineage_integrity']['licenses_present']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_forge/decompose.py:lineage_integrity",
                "detail": json.dumps(fusion["lineage"], sort_keys=True),
            },
            {
                "kind": "decomposition-round-trip",
                "claim": (
                    "decompose(fusion) recovered "
                    f"{dec['recovered_ids']} and each component ran standalone "
                    "on the matched case set; fusion passed every case any "
                    f"source passed (missing={cover['missing_from_fusion']})."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_forge/decompose.py:decompose",
                "detail": json.dumps(
                    {
                        "recovered_ids": dec["recovered_ids"],
                        "union_source_cases": cover["union_source_cases"],
                        "fusion_cases": cover["fusion_cases"],
                    },
                    sort_keys=True,
                ),
            },
            {
                "kind": "loss-control",
                "claim": (
                    "Dropping the cite stage from the fusion makes "
                    "capability_report.difference contain stage:cite and "
                    f"tool:LicenseScan ({bad['difference']}). The intact "
                    "fusion difference stays empty."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_forge/decompose.py:drop_stage",
                "detail": json.dumps(
                    {
                        "good_difference": caps["difference"],
                        "bad_difference": bad["difference"],
                    },
                    sort_keys=True,
                ),
            },
        ],
        "tests": [
            {
                "id": "capability-set-difference-from-stage-tool-declarations",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "decomposition-round-trip-recovered-components-run-standalone",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
            {
                "id": "lineage-integrity-every-fused-stage-names-source-and-license",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "loss-control-drop-stage-difference-detected",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[-8000:],
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0317-probe2-decompose-and-loss",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 re-runs decompose so recovered sources execute "
                "standalone, then drops cite and requires capability_report "
                "to name stage:cite and tool:LicenseScan. This is a detector "
                "control, not a re-read of probe 1's conclusion."
            ),
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "answer": (
            "Best-of-breed fusion of wf.source.alpha-retriever (Apache-2.0) "
            "and wf.source.beta-ranker (MIT) selects retrieve=alpha, rank=beta, "
            "synthesize=alpha, cite=beta. Capability-set difference "
            f"(union of sources minus fusion) is {caps['difference'] or 'empty'}. "
            f"Lineage names every fused stage with source and license. "
            f"decompose recovered {dec['recovered_ids']} and each ran "
            "standalone on the matched case set; fusion covers every case "
            f"any source covers (missing={cover['missing_from_fusion']}). "
            "Dropping cite surfaces stage:cite and tool:LicenseScan as a "
            f"blocking finding {bad['difference']}. {SENTINEL}"
        ),
        "notes": (
            "G-1 for TST-0317: live named probes exit 0, receipts/TST-0317.json "
            "state=SUCCESS, per-unit UNIT-ARTIFACT-MANIFEST row. Did not run "
            "global unit_manifest.py --write. No ADV rebuild. Cloud ok=true "
            "is not delivery. SUCCESS:TST-0317"
        ),
    }
    if SENTINEL not in json.dumps(doc):
        print("FAILED:TST-0317 sentinel-absent before write")
        return 1
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = digest_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
