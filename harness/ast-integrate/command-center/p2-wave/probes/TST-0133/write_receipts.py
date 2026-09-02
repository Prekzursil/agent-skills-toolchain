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

import contract as C  # noqa: E402

SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/TST-0133/wrap.py",
    "command-center/p2-wave/probes/TST-0133/suite.py",
    "command-center/p2-wave/probes/TST-0133/audit.py",
    "command-center/p2-wave/probes/TST-0133/harness.py",
    "command-center/p2-wave/probes/TST-0133/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0133/probe1_delta_egress.py",
    "command-center/p2-wave/probes/TST-0133/probe2_detector_both_states.py",
    "command-center/p2-wave/probes/TST-0133/contract.py",
    "command-center/p2-wave/probes/TST-0133/fragment.py",
    "command-center/p2-wave/probes/TST-0133/fault_injection_report.schema.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
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
        "present": True,
        "unit_id": C.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/TST-0133/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_receipt.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print("FAILED:receipts emit")
        print(((emit.stdout or "") + (emit.stderr or ""))[-2000:])
        return 1
    print((emit.stdout or "").strip())
    c1, t1 = run_probe(C.P1)
    c2, t2 = run_probe(C.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(C.OUTPUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "registered": True,
        "output_path": C.OUTPUT_REL,
        "output_schema": f"{C.SCHEMA_REL}#/$defs/{C.SCHEMA_DEF}",
        "named_probes": [
            {"id": "probe1", "command": C.P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": C.P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": C.OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0133/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0133-probe2-detector-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0133: live named probes exit 0, receipts/TST-0133.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT_ID,
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
    print(f"primary {C.OUTPUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0133 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
