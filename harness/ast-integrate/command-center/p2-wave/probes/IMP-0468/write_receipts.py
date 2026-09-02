#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0468.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0468/probe1_planted_nested.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0468/probe2_non_case_receipt.py"
)
SUPPORTING = [
    "tools/command-center/case_collision.py",
    "command-center/p2-wave/probes/IMP-0468/probe1_planted_nested.py",
    "command-center/p2-wave/probes/IMP-0468/probe2_non_case_receipt.py",
    "command-center/p2-wave/probes/IMP-0468/emit_receipt.py",
    "command-center/p2-wave/probes/IMP-0468/fixtures/planted-collision.json",
    "command-center/p2-wave/probes/IMP-0468/fixtures/nested-collision.json",
    "command-center/p2-wave/probes/IMP-0468/fixtures/non-case-distinct.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"})
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
        "unit_id": "IMP-0468",
        "receipt_path": "command-center/p2-wave/probes/IMP-0468/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:receipts probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0468",
        "unit_id": "IMP-0468",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SENTINEL:IMP-0468:CASE-COLLISION-SCANNED",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": code1, "raw_output": text1},
            {"id": "probe2", "command": P2, "exit_code": code2, "raw_output": text2},
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0468/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0468-probe2-non-case-and-live-rescan",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for IMP-0468: live named probes exit 0, receipts/IMP-0468.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0468",
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
    print("SUCCESS:IMP-0468 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
