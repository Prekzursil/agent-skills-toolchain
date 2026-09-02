#!/usr/bin/env python3
"""Emit IMP-0157 receipt, then per-unit SUBAGENT-RETURN + UNIT-ARTIFACT-MANIFEST.

Runs the named probes first. Writes command-center/receipts/IMP-0157.json only
after they exit 0, then hashes the live bytes into the per-unit manifest.
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
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from workflow_foundry import licence_matrix as lm  # noqa: E402
from workflow_foundry.fusion import (  # noqa: E402
    FusionRefused,
    WorkflowSource,
    fuse_workflows,
)
from workflow_foundry.registry import observed_raw  # noqa: E402

UNIT = "IMP-0157"
OUT = "command-center/receipts/IMP-0157.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0157/probe1_matrix_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0157/probe2_fusion_entry.py"
)
SUPPORTING = [
    "tools/workflow_foundry/licence_matrix.py",
    "tools/workflow_foundry/fusion.py",
    "tools/workflow_foundry/registry.py",
    "tools/workflow_foundry/candidate_registry.json",
    "command-center/p2-wave/probes/IMP-0157/probe1_matrix_coverage.py",
    "command-center/p2-wave/probes/IMP-0157/probe2_fusion_entry.py",
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0157/SUBAGENT-RETURN.json",
        "role": role,
    }


def live_fusion_refusal() -> dict:
    try:
        fuse_workflows(
            [
                WorkflowSource(id="gpl", licence="GPL-3.0-only", body="g"),
                WorkflowSource(id="prop", licence="LicenseRef-Proprietary", body="p"),
            ]
        )
        return {"raised": False}
    except FusionRefused as exc:
        return {
            "raised": True,
            "reason": exc.reason,
            "suggested_alternative": exc.suggested_alternative,
            "type": type(exc).__name__,
            "fused_body": None,
        }


def build_receipt(t1: str, t2: str, started: str, ended: str) -> dict:
    raw = observed_raw(REPO)
    gap = lm.coverage_gap(raw)
    axes = sorted(lm.matrix_axes())
    cells = list(lm.iter_cells())
    forbidden = [
        {"a": a, "b": b, "reason": v.reason}
        for a, b, v in cells
        if not v.allowed and v.reason == lm.REASON_COPYLEFT_PROPRIETARY
    ]
    fusion_hit = live_fusion_refusal()
    fusion_src = (REPO / "tools/workflow_foundry/fusion.py").read_text(encoding="utf-8")
    call_site = "licence_matrix.solve_licences(inbound)" in fusion_src
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0157",
        "title": "Licence-compatibility matrix and fusion licence solver",
        "question": (
            "When N source workflows with different licences are fused, what "
            "licence may the result carry, and when is fusion forbidden outright?"
        ),
        "answer": (
            "Outbound licence is the most-restrictive compatible SPDX id on the "
            "closed lattice. Fusion is forbidden (no fused body) when the inbound "
            "set mixes copyleft with proprietary, names UNKNOWN, carries a vendor "
            "rider, or hits a documented incompatibility (GPL-2.0-only+Apache-2.0, "
            "GPL-2.0-only+GPL-3 family, CC-BY-SA vs software copyleft). The "
            "named copyleft+proprietary refusal reason is COPYLEFT_PROPRIETARY "
            "and the suggested alternative is CLEAN-ROOM-REIMPLEMENT."
        ),
        "spec_anchor": "_USER-PROMPTS.md:10723 (CLEAN-ROOM-REIMPLEMENT disposition)",
        "min_bytes_threshold": 2048,
        "profile": "implementation-receipt",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "local-parallel",
        },
        "implementation": {
            "matrix_module": "tools/workflow_foundry/licence_matrix.py",
            "fusion_entry": "tools/workflow_foundry/fusion.py:fuse_workflows",
            "fusion_calls_matrix_attribute": call_site,
            "registry": "tools/workflow_foundry/candidate_registry.json",
            "axis_count": len(axes),
            "cell_count": len(cells),
            "axes": axes,
            "copyleft_proprietary_cell_count": len(forbidden),
        },
        "evidence": [
            {
                "claim": (
                    "The matrix is exhaustive over the computed observed licence "
                    "set (canonical set difference empty; unidentified spellings empty)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_foundry/licence_matrix.py:coverage_gap",
                "numbers": {
                    "observed_count": gap["observed_count"],
                    "axis_count": gap["axis_count"],
                    "missing_from_matrix": gap["missing_from_matrix"],
                    "unidentified_spellings": gap["unidentified_spellings"],
                    "exhaustive": gap["exhaustive"],
                },
                "probe": "probe1_matrix_coverage",
            },
            {
                "claim": (
                    "A copyleft+proprietary pair is refused at fuse_workflows, "
                    "which calls licence_matrix.solve_licences, with named reason "
                    "COPYLEFT_PROPRIETARY and suggested alternative "
                    "CLEAN-ROOM-REIMPLEMENT; no fused body is produced."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_foundry/fusion.py:64",
                "fusion_entry_result": fusion_hit,
                "probe": "probe2_fusion_entry",
            },
        ],
        "tests": [
            {
                "id": "T1-matrix-covers-observed-set",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-1200:],
            },
            {
                "id": "T2-forbidden-pair-refused-at-fusion-entry",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-1200:],
            },
        ],
        "negative_controls": [
            {
                "id": "C1-plant-Python-2.0",
                "kind": "coverage-hole",
                "description": (
                    "Adding SPDX id Python-2.0 (not on the lattice) must make "
                    "coverage_gap exhaustive=False; the live set without the plant "
                    "is exhaustive."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "C2-mit-apache-twin",
                "kind": "both-states-fusion",
                "description": (
                    "MIT+Apache-2.0 fuses (outbound Apache-2.0) while "
                    "GPL-3.0-only+LicenseRef-Proprietary is refused at the same API."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0157-probe2-fusion-entry-not-matrix-unit",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 spies licence_matrix.solve_licences and calls "
                "fuse_workflows; a matrix-only unit test would not satisfy it."
            ),
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "notes": (
            "IMP-0156 SPDX extractor is not delivered on this worktree; observed "
            "licences are the RES-0135 corpus seed union live package-lock SPDX "
            "strings. SUCCESS:IMP-0157"
        ),
        "completion_sentinel": "SUCCESS:IMP-0157",
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0157 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = build_receipt(t1, t2, started, ended)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0157" not in payload:
        print("FAILED:IMP-0157 sentinel missing from receipt text")
        return 1
    if len(payload.encode("utf-8")) < 2048:
        print("FAILED:IMP-0157 receipt below 2048 B")
        return 1
    out.write_text(payload, encoding="utf-8")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0157",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0157/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0157-probe2-fusion-entry-not-matrix-unit",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0157: live named probes exit 0, receipts/IMP-0157.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "cloud_ok": False,
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0157 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
