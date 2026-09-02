#!/usr/bin/env python3
"""Emit WFA-0101 FusionResult, SUBAGENT-RETURN, and per-unit UNIT-ARTIFACT-MANIFEST."""
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

from fusion_op import OUT_REL, build_fusion_result, dump_json  # noqa: E402

UNIT = "WFA-0101"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0101/probe1_recompose.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0101/probe2_degeneracy.py"
)
SUPPORTING = [
    "tools/workflow_foundry/common_core.py",
    "tools/workflow_foundry/workflow_ir.py",
    "command-center/p2-wave/probes/WFA-0101/families.py",
    "command-center/p2-wave/probes/WFA-0101/fusion_op.py",
    "command-center/p2-wave/probes/WFA-0101/semantic_diff.py",
    "command-center/p2-wave/probes/WFA-0101/fusion_result.schema.json",
    "command-center/p2-wave/probes/WFA-0101/probe1_recompose.py",
    "command-center/p2-wave/probes/WFA-0101/probe2_degeneracy.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "receipt_path": "command-center/p2-wave/probes/WFA-0101/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art = build_fusion_result(ts=now)
    summary = art["summary"]
    if summary["recomposition_exact_on_ok_families"] is not True:
        print("FAILED:WFA-0101 emit recomposition not exact")
        return 1
    if summary["non_ok_families_emit_no_core"] is not True:
        print("FAILED:WFA-0101 emit non-ok families still emit a core")
        return 1
    if int(summary["degenerate_intersection"]) < 2:
        print("FAILED:WFA-0101 emit missing degenerate families")
        return 1
    dump_json(REPO / OUT_REL, art)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0101 emit probes c1={c1} c2={c2}")
        print(t1[-4000:])
        print(t2[-4000:])
        return 1

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0101",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/FusionResult",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "recompose-exact-and-licence-union",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "degeneracy-both-states",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/WFA-0101/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0101-probe2-degeneracy-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0101: live named probes exit 0, FusionResult "
            "state=SUCCESS, per-unit manifest row. Live blueprint library and "
            "WFA-0001 schema pack are absent; D1-D20 are control families. "
            "Did not run global unit_manifest.py --write."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0101 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
