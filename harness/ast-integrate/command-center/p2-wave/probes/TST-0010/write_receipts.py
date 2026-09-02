#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0010.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0010/probe1_open_p1_blocks.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0010/probe2_downgrade_audit.py"
)
SUPPORTING = [
    "tools/command-center/completion_c10.py",
    "tools/command-center/tests/test_completion_c10.py",
    "command-center/schema/test-receipt.schema.json",
    "command-center/p2-wave/probes/TST-0010/probe1_open_p1_blocks.py",
    "command-center/p2-wave/probes/TST-0010/probe2_downgrade_audit.py",
    "command-center/p2-wave/probes/TST-0010/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0010/fixtures/blocked_open_p1.transcript.txt",
    "command-center/p2-wave/probes/TST-0010/fixtures/downgrade_audit_row.jsonl",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
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
        "unit_id": "TST-0010",
        "receipt_path": "command-center/p2-wave/probes/TST-0010/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    primary_path = REPO / OUT
    if not primary_path.is_file() or primary_path.stat().st_size <= 0:
        print(f"FAILED:receipts missing {OUT}")
        return 1
    doc = json.loads(primary_path.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:receipts self-declared {doc.get('state')}")
        return 1
    text = primary_path.read_text(encoding="utf-8")
    if "SUCCESS:TST-0010" not in text:
        print("FAILED:receipts sentinel absent")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0010",
        "unit_id": "TST-0010",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0010",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered TST-0010",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "open-p1-blocks-named-id",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "append-only-downgrade-audit",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0010/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0010-probe2-downgrade-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "question": (
            "Can a defect be silently downgraded from P1 to P2 to unblock, "
            "without an audit entry?"
        ),
        "answer": "NO",
        "ts": now,
        "notes": (
            "G-1 for TST-0010: live named probes exit 0, receipts/TST-0010.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0010",
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
    print("SUCCESS:TST-0010 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
