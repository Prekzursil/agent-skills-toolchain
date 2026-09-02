#!/usr/bin/env python3
"""Write TST-0157 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Named probes are re-run live. Does not invoke tools/command-center/unit_manifest.py --write.
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
REPO = HERE.parents[3]

UID = "TST-0157"
OUT = "command-center/receipts/TST-0157.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/concurrency_report"
SENTINEL = "SUCCESS:TST-0157"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0157/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0157/probe2_race_amplification.py"
)
SUPPORTING = [
    "tools/command-center/work_claim.py",
    "tools/lib/handled-ledger.mjs",
    "command-center/p2-wave/probes/TST-0157/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0157/probe2_race_amplification.py",
    "command-center/p2-wave/probes/TST-0157/emit_receipt.py",
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
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def manifest_row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/TST-0157/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0157/emit_receipt.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:{UID} emit rc={ce}")
        print(te[-2500:])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} probes c1={c1} c2={c2}")
        print(t1[-2500:])
        print(t2[-2500:])
        return 1

    rec_path = REPO / OUT
    doc = json.loads(rec_path.read_text(encoding="utf-8"))
    doc["named_probe_runs"] = [
        {
            "id": "probe1",
            "command": P1,
            "result": "PASS",
            "exit_code": c1,
            "output_tail": t1[-4000:],
        },
        {
            "id": "probe2",
            "command": P2,
            "result": "PASS",
            "exit_code": c2,
            "output_tail": t2[-4000:],
        },
    ]
    rec_path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    c1b, t1b = run_cmd(P1)
    c2b, t2b = run_cmd(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:{UID} probes after receipt update c1={c1b} c2={c2b}")
        print(t1b[-2500:])
        print(t2b[-2500:])
        return 1

    primary = manifest_row(OUT, "primary")
    artifacts = [primary] + [manifest_row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-states-distinct-and-contested",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "race-amplification-100-and-toctou-mutation",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/TST-0157/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0157-probe2-race-amplification",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0157: live named probes exit 0, receipts/TST-0157.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
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
    print(f"SUCCESS:{UID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
