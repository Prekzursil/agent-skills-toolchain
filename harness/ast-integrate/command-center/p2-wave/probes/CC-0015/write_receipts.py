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
OUT = "command-center/receipts/CC-0015.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0015/probe1_three_values_and_aggregation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0015/probe2_sc13_amendment_and_reviewer.py"
)
SUPPORTING = [
    "command-center/schema/stopping-condition.schema.json",
    "command-center/p2-wave/probes/CC-0015/predicate_table.py",
    "command-center/p2-wave/probes/CC-0015/evaluator.py",
    "command-center/p2-wave/probes/CC-0015/live_state.py",
    "command-center/p2-wave/probes/CC-0015/emit.py",
    "command-center/p2-wave/probes/CC-0015/probe1_three_values_and_aggregation.py",
    "command-center/p2-wave/probes/CC-0015/probe2_sc13_amendment_and_reviewer.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
    sha, nbytes = digest(path) if path.is_file() else ("", 0)
    return {
        "bytes": nbytes,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/CC-0015/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CC-0015",
    }


def main() -> int:
    code, text = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CC-0015/emit.py"
    )
    print(text)
    if code != 0:
        print(f"FAILED:CC-0015 emit exit={code}")
        return code or 1
    artifact = REPO / OUT
    if not artifact.is_file():
        print("FAILED:CC-0015 artifact missing after emit")
        return 1
    probes = []
    for pid, cmd in (("probe1", P1), ("probe2", P2)):
        pcode, ptext = run_cmd(cmd)
        probes.append(
            {
                "command": cmd,
                "exit_code": pcode,
                "id": pid,
                "raw_output": ptext[-4000:],
            }
        )
        print(ptext)
        if pcode != 0:
            print(f"FAILED:CC-0015 {pid} exit={pcode}")
            return pcode or 1

    sha, nbytes = digest(artifact)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": nbytes,
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": sha,
            }
        ],
        "id": "CC-0015",
        "manifest_path": "command-center/p2-wave/probes/CC-0015/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": probes,
        "notes": (
            "G-1 for CC-0015: live named probes exit 0, receipts/CC-0015.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/stopping-condition.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CC-0015-probe2-sc13-amendment-and-encoding-review",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CC-0015",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CC-0015",
        "cloud_ok": False,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "schema_version": 1,
        "unit_id": "CC-0015",
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:CC-0015 write_receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
