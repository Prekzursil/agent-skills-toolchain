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
OUT = "command-center/receipts/TST-0023.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0023/probe1_every_field_declares_anchoring.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0023/probe2_recapture_same_sha.py"
)
SUPPORTING = [
    "command-center/schema/baseline-snapshot.schema.json",
    "command-center/schema/test-receipt.schema.json",
    "tools/baseline/capture.py",
    "tools/baseline/anchoring.py",
    "tools/baseline/__init__.py",
    "command-center/p2-wave/probes/TST-0023/probe1_every_field_declares_anchoring.py",
    "command-center/p2-wave/probes/TST-0023/probe2_recapture_same_sha.py",
    "command-center/p2-wave/probes/TST-0023/fixtures.py",
    "command-center/p2-wave/probes/TST-0023/emit_receipt.py",
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
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "TST-0023",
        "receipt_path": "command-center/p2-wave/probes/TST-0023/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        print("FAILED:TST-0023 write_receipts missing catalog artifact")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0023 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0023",
        "unit_id": "TST-0023",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0023",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/test-receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "every-field-declares-anchoring-kind",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "recapture-same-sha-reproduces-anchored-fields",
                "raw_output": t2[-8000:],
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
        "manifest_path": "command-center/p2-wave/probes/TST-0023/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0023-probe2-recapture-same-sha",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0023: live named probes exit 0, receipts/TST-0023.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0023",
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
    print(
        f"wrote SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json "
        f"primary_sha={primary['sha256']} rows={len(artifacts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
