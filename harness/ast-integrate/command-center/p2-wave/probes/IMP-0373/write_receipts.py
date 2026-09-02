#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for IMP-0373."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/IMP-0373.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0373/probe1_apply_revert_tree_hash.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0373/probe2_incomplete_revert_caught.py"
)
SUPPORTING = [
    "tools/selfimprove/retain.py",
    "tools/selfimprove/__init__.py",
    "tools/selfimprove/tests/test_retain.py",
    "command-center/p2-wave/probes/IMP-0373/fixture.py",
    "command-center/p2-wave/probes/IMP-0373/probe1_apply_revert_tree_hash.py",
    "command-center/p2-wave/probes/IMP-0373/probe2_incomplete_revert_caught.py",
    "command-center/p2-wave/probes/IMP-0373/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "IMP-0373",
        "receipt_path": "command-center/p2-wave/probes/IMP-0373/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    tests = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B tools/selfimprove/tests/test_retain.py"
    )
    if tests[0] != 0:
        print(f"FAILED:receipts tests rc={tests[0]}")
        print(tests[1][-2000:])
        return 1
    emit = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/IMP-0373/emit_receipt.py"
    )
    if emit[0] != 0:
        print(f"FAILED:receipts emit rc={emit[0]}")
        print(emit[1][-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "IMP-0373",
        "unit_id": "IMP-0373",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0373",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=selfimprove-retention-module"
        ),
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
        "manifest_path": "command-center/p2-wave/probes/IMP-0373/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0373-probe2-incomplete-revert-and-safety",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0373: live named probes exit 0, receipts/IMP-0373.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. retain.py keeps a change only when "
            "improvement is measured; revert restores byte-identical trees "
            "and does not touch non-candidate files."
        ),
        "tests_raw": tests[1],
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0373",
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
    print("SUCCESS:IMP-0373 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
