#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
OUT = "command-center/research/RES-0065.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0065/probe1_dual_rail_mapping.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0065/probe2_control_overclaim.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0065/common.py",
    "command-center/p2-wave/probes/RES-0065/probe1_dual_rail_mapping.py",
    "command-center/p2-wave/probes/RES-0065/probe2_control_overclaim.py",
    "command-center/p2-wave/probes/RES-0065/captures/INDEX.json",
    "command-center/p2-wave/probes/ARC-0010/registry.json",
    "command-center/p2-wave/probes/ARC-0016/fixtures/hatch-run/typed/workflows/wf.catalog-class.discovery-only.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env
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
        "unit_id": "RES-0065",
        "receipt_path": "command-center/p2-wave/probes/RES-0065/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_tests(c1: int, c2: int) -> None:
    art = REPO / OUT
    doc = json.loads(art.read_text(encoding="utf-8"))
    for t in doc.get("tests") or []:
        if t.get("id") == "T-PROBE-1-DUAL-RAIL-MAPPING":
            t["result"] = "PASS" if c1 == 0 else "FAIL"
        elif t.get("id") == "T-PROBE-2-CONTROL-OVERCLAIM":
            t["result"] = "PASS" if c2 == 0 else "FAIL"
    art.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    patch_tests(c1, c2)
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0065",
        "unit_id": "RES-0065",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0065",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0065/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0065-probe2-control-and-rail-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0065: live named probes exit 0, research artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Dual rails are SchemaStore/Git refs API "
            "plus commit-pinned github/docs markdown. No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0065",
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
    print("SUCCESS:RES-0065 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
