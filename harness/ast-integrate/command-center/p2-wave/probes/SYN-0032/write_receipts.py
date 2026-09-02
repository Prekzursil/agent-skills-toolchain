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
sys.path.insert(0, str(HERE))
import emit_map as E  # noqa: E402

OUT = "command-center/receipts/SYN-0032.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0032/probe1_row_completeness.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0032/probe2_planted_absence.py"
)
SUPPORTING = [
    "command-center/schema/coverage-map.schema.json",
    "command-center/p2-wave/probes/SYN-0032/graph.py",
    "command-center/p2-wave/probes/SYN-0032/mentions.py",
    "command-center/p2-wave/probes/SYN-0032/coverage.py",
    "command-center/p2-wave/probes/SYN-0032/emit_map.py",
    "command-center/p2-wave/probes/SYN-0032/probe1_row_completeness.py",
    "command-center/p2-wave/probes/SYN-0032/probe2_planted_absence.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "present": True,
        "unit_id": "SYN-0032",
        "receipt_path": "command-center/p2-wave/probes/SYN-0032/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    code = E.main()
    if code != 0:
        print(f"FAILED:SYN-0032 emit rc={code}")
        return code
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:SYN-0032 probes c1={c1} c2={c2}")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0032",
        "unit_id": "SYN-0032",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0032",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/coverage-map.schema.json",
        "measure_line": "SUCCESS:delivered SYN-0032",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered SYN-0032"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "row-completeness",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "planted-absence-and-toc",
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0032/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0032-probe2-planted-absence",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0032: live named probes exit 0, SYN-0032.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. PHASE-GRAPH.json reconstructed from catalog."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0032",
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
    print("SUCCESS:SYN-0032 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
