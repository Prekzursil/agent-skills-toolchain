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
OUT = "command-center/receipts/CC-0003.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0003/probe1_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0003/probe2_antipatterns.py"
)
SUPPORTING = [
    "platform/lib/completion_predicate.py",
    "platform/lib/fanin/local_runner.py",
    "platform/lib/fanin/cloud_dispatcher.py",
    "platform/lib/fanin/monitor.py",
    "platform/lib/fanin/harvester.py",
    "platform/lib/fanin/workflow_fanin.py",
    "platform/lib/fanin/cross_vendor_adapter.py",
    "platform/lib/fanin/final_synthesis.py",
    "command-center/p2-wave/probes/CC-0003/scenario.py",
    "command-center/p2-wave/probes/CC-0003/probe1_table.py",
    "command-center/p2-wave/probes/CC-0003/probe2_antipatterns.py",
    "command-center/p2-wave/probes/CC-0003/emit_receipt.py",
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
        "unit_id": "CC-0003",
        "receipt_path": "command-center/p2-wave/probes/CC-0003/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary_path = REPO / OUT
    if not primary_path.is_file() or primary_path.stat().st_size <= 0:
        print(f"FAILED:receipts missing {OUT}")
        return 1
    doc = json.loads(primary_path.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:receipts self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CC-0003" not in primary_path.read_text(encoding="utf-8"):
        print("FAILED:receipts sentinel absent")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CC-0003",
        "unit_id": "CC-0003",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0003",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "table-driven-falsifiers",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "antipatterns-and-fanin-identity",
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
        "manifest_path": "command-center/p2-wave/probes/CC-0003/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CC-0003-probe2-antipatterns",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CC-0003: live named probes exit 0, CC-0003.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CC-0003",
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
    print("SUCCESS:CC-0003 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
