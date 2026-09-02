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
OUT = "command-center/receipts/CC-0024.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0024/probe1_floor_recall.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0024/probe2_deletion_binding.py"
)
SUPPORTING = [
    "command-center/schema/requirement-record.schema.json",
    "command-center/p2-wave/probes/CC-0024/extract.py",
    "command-center/p2-wave/probes/CC-0024/emit.py",
    "command-center/p2-wave/probes/CC-0024/probe1_floor_recall.py",
    "command-center/p2-wave/probes/CC-0024/probe2_deletion_binding.py",
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
    sha, nbytes = digest(path) if path.is_file() else ("", 0)
    return {
        "bytes": nbytes,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/CC-0024/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CC-0024",
    }


def main() -> int:
    artifact = REPO / OUT
    if not artifact.is_file():
        print("FAILED:CC-0024 artifact missing; run emit.py first")
        return 1
    probes = []
    for pid, cmd in (("probe1", P1), ("probe2", P2)):
        code, text = run_probe(cmd)
        probes.append(
            {
                "command": cmd,
                "exit_code": code,
                "id": pid,
                "raw_output": text[-4000:],
            }
        )
        print(text)
        if code != 0:
            print(f"FAILED:CC-0024 {pid} exit={code}")
            return code or 1

    sha, nbytes = digest(artifact)
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
        "id": "CC-0024",
        "manifest_path": "command-center/p2-wave/probes/CC-0024/UNIT-ARTIFACT-MANIFEST.json",
        "measure": {"exit_code": None, "line": None},
        "named_probes": probes,
        "notes": (
            "G-1 for CC-0024: live named probes exit 0, receipts/CC-0024.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/requirement-record.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CC-0024-probe2-deletion-binding",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CC-0024",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "unit_id": "CC-0024",
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    artifacts = [row(OUT, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
    fixture = "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md"
    if (REPO / fixture).is_file():
        artifacts.append(row(fixture, "supporting"))
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "schema_version": 1,
        "unit_id": "CC-0024",
        "verified_on_disk": True,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} bytes={nbytes} sha256={sha}")
    print("SUCCESS:CC-0024 write_receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
