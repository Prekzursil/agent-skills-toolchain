#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
UNIT = "WFA-0080"
OUT = "command-center/wfa/WFA-0080-semantic-component-graph.json"
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0080/emit_graph.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0080/probe1_vocabulary_closure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0080/probe2_structure_and_substitution.py"
)
SUPPORTING = [
    SCHEMA_REL := "command-center/p2-wave/probes/WFA-0080/graph.schema.json",
    "command-center/p2-wave/probes/WFA-0080/semantic_graph.py",
    "command-center/p2-wave/probes/WFA-0080/emit_graph.py",
    "command-center/p2-wave/probes/WFA-0080/probe1_vocabulary_closure.py",
    "command-center/p2-wave/probes/WFA-0080/probe2_structure_and_substitution.py",
    "command-center/p2-wave/probes/WFA-0080/fixtures/workflow_compat_signature.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/WFA-0080/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c0, t0 = run_cmd(EMIT)
    if c0 != 0:
        print(f"FAILED:receipts emit c0={c0}")
        print(t0[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0080",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/Graph",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "vocabulary-closure-endpoints-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-bfs-not-isomorphic-worked-substitution",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0080/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0080-probe2-structure-and-substitution",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog tests_required, not the author summary",
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0080: live named probes exit 0, semantic component "
            "graph state=SUCCESS with SUCCESS:WFA-0080, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. Vocabulary is "
            "catalog-grounded reconstruction; upstream WFA-0058/59/62/66 "
            "artifacts are absent. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0080 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
