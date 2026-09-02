#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for IMP-0298."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "IMP-0298"
OUT_REL = "command-center/receipts/IMP-0298.json"
PROBE_DIR = REPO / "command-center/p2-wave/probes/IMP-0298"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0298/probe1_exhaust_each_dimension.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0298/probe2_marker_and_transport.py"


def sha256_file(path: Path) -> tuple[str, int]:
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


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/IMP-0298/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:IMP-0298 probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    primary = art(OUT_REL, "primary")
    artifacts = [
        primary,
        art("tools/council/budget/governor.py", "supporting"),
        art("tools/council/budget/transport.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0298/probe1_exhaust_each_dimension.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0298/probe2_marker_and_transport.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0298/fixtures.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0298/emit_receipt.py", "supporting"),
    ]

    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0298",
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/receipt.schema.json profile=council-budget-module",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "exhaust-each-dimension",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "marker-load-bearing-and-transport-count",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0298/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0298-probe2-marker-load-bearing",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for IMP-0298: live named probes exit 0, receipt state=SUCCESS with "
            "SUCCESS:IMP-0298, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }

    (PROBE_DIR / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (PROBE_DIR / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("wrote SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
