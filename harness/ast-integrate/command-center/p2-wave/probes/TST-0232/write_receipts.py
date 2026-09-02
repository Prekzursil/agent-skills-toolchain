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

OUT = C.OUTPUT_REL
P1 = C.P1
P2 = C.P2
SUPPORTING = [
    C.LOCAL_SCHEMA_REL,
    C.VISIBLE_PREFIX_FILE,
    C.HOLDOUT_PREFIX_FILE,
    "command-center/p2-wave/probes/TST-0232/contract.py",
    "command-center/p2-wave/probes/TST-0232/corpus.py",
    "command-center/p2-wave/probes/TST-0232/gate.py",
    "command-center/p2-wave/probes/TST-0232/provenance.py",
    "command-center/p2-wave/probes/TST-0232/probe1_overfit_gap.py",
    "command-center/p2-wave/probes/TST-0232/probe2_holdout_provenance.py",
    "command-center/p2-wave/probes/TST-0232/emit_receipt.py",
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
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0232/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": C.UNIT_ID,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:TST-0232 receipts: {OUT} missing; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0232 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = artifacts[0]
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": C.UNIT_ID,
        "manifest_path": "command-center/p2-wave/probes/TST-0232/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "overfit-gap-detector",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "holdout-provenance",
            },
        ],
        "notes": (
            "G-1 for TST-0232: live named probes exit 0, receipts/TST-0232.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
        "output_path": OUT,
        "output_schema": C.LOCAL_SCHEMA_REL,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0232-probe2-holdout-provenance",
            "verdict": "PASS",
        },
        "sentinel": C.SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": C.UNIT_ID,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": C.UNIT_ID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0232 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
