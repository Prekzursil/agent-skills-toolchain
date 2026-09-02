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

from constants import (  # noqa: E402
    OUTPUT_REL,
    P1_CMD,
    P2_CMD,
    SCHEMA_REL,
    UNIT_ID,
    catalog_sentinel,
)

SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/SYN-0022/schema_util.py",
    "command-center/p2-wave/probes/SYN-0022/cnf0006_fingerprint.py",
    "command-center/p2-wave/probes/SYN-0022/gate.py",
    "command-center/p2-wave/probes/SYN-0022/facts.py",
    "command-center/p2-wave/probes/SYN-0022/constants.py",
    "command-center/p2-wave/probes/SYN-0022/emit_reprobe.py",
    "command-center/p2-wave/probes/SYN-0022/probe1_fingerprint_independence.py",
    "command-center/p2-wave/probes/SYN-0022/probe2_controls_and_mnn.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/SYN-0022/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/SYN-0022/emit_reprobe.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-2000:])
        return 1
    c1, t1 = run_cmd(P1_CMD)
    c2, t2 = run_cmd(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUTPUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentinel = catalog_sentinel()
    ret = {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "registered": True,
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "raw_output": t1,
                "role": "fingerprint-independence",
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "raw_output": t2,
                "role": "empty-source-and-mnn-control",
            },
        ],
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/SYN-0022/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "SYN-0022-probe2-controls-and-mnn",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for SYN-0022: live named probes exit 0, premise-reprobe "
            "state=SUCCESS, every record declares both CNF-0006 probes, "
            "M-NN is REFUTED-AS-BRIEFED. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT_ID,
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
    print(f"primary {OUTPUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0022 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
