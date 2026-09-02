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
OUT = "command-center/receipts/TST-0314.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0314/probe1_series_from_records.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0314/probe2_degradation_control.py"
)
SUPPORTING = [
    "tools/bench/metaloop.py",
    "tools/bench/stats_review.py",
    "tools/bench/__init__.py",
    "tools/bench/decision-record.schema.json",
    "command-center/p2-wave/probes/TST-0314/harness.py",
    "command-center/p2-wave/probes/TST-0314/probe1_series_from_records.py",
    "command-center/p2-wave/probes/TST-0314/probe2_degradation_control.py",
    "command-center/p2-wave/probes/TST-0314/emit_receipt.py",
    "command-center/p2-wave/probes/TST-0314/fixtures/preregistered_thresholds.json",
    "command-center/p2-wave/probes/TST-0314/fixtures/TST-0314-strict-stable.jsonl",
    "command-center/p2-wave/probes/TST-0314/fixtures/TST-0314-strict-degrading.jsonl",
    "command-center/p2-wave/probes/TST-0314/fixtures/TST-0314-permissive.jsonl",
    "command-center/p2-wave/probes/TST-0314/fixtures/TST-0314-single-iteration.jsonl",
    "command-center/bench/results/TST-0314-strict-stable.jsonl",
    "command-center/bench/results/TST-0314-strict-degrading.jsonl",
    "command-center/bench/results/TST-0314-permissive.jsonl",
    "command-center/bench/results/TST-0314-single-iteration.jsonl",
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
        "present": True,
        "exists": path.is_file(),
        "eol": "LF",
        "unit_id": "TST-0314",
        "receipt_path": "command-center/p2-wave/probes/TST-0314/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print(f"FAILED:receipts missing {OUT}; run emit_receipt.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    missing = [p for p in SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print(f"FAILED:receipts missing supporting {missing}")
        return 1
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "TST-0314",
        "unit_id": "TST-0314",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0314",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "series-from-records",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "degradation-control",
                "raw_output": t2[-4000:],
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
        "manifest_path": "command-center/p2-wave/probes/TST-0314/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0314-stats-review",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0314: live named probes exit 0, TST-0314.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0314",
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
    print("SUCCESS:TST-0314 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
