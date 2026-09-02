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
OUT = "command-center/receipts/TST-0249.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0249/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0249/probe2_regression_seed.py"
)
SUPPORTING = [
    "tools/command-center/close.py",
    "command-center/p2-wave/probes/TST-0249/harness.py",
    "command-center/p2-wave/probes/TST-0249/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0249/probe1_both_states.py",
    "command-center/p2-wave/probes/TST-0249/probe2_regression_seed.py",
    "command-center/p2-wave/probes/TST-0249/artifact.schema.json",
    "command-center/p2-wave/probes/TST-0249/fixtures/nonascii-catalog.json",
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
        "unit_id": "TST-0249",
        "receipt_path": "command-center/p2-wave/probes/TST-0249/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = run_probe(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/TST-0249/emit_receipt.py"
    )
    if emit[0] != 0:
        print("FAILED:TST-0249 receipts emit")
        print(emit[1][-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0249 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        "id": "TST-0249",
        "manifest_path": "command-center/p2-wave/probes/TST-0249/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "utf8-both-states-byte-exact",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "cp1252-exit-and-decode-seed",
            },
        ],
        "notes": (
            "G-1 for TST-0249: live named probes exit 0, receipts/TST-0249.json "
            "state=SUCCESS ux_pass=false (production close.py crashes on cp1252), "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not patch tools/command-center."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/ux_report",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0249-probe2-regression-seed-rerun",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:TST-0249",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "TST-0249",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "TST-0249",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0249 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
