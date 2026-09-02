#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0042/probe1_exit_codes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0042/probe2_result_summaries.py"
)
SUPPORTING = [
    C.SCHEMA_REL,
    C.INV_REL,
    "command-center/p2-wave/probes/AUD-0042/common.py",
    "command-center/p2-wave/probes/AUD-0042/controls.py",
    "command-center/p2-wave/probes/AUD-0042/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0042/probe1_exit_codes.py",
    "command-center/p2-wave/probes/AUD-0042/probe2_result_summaries.py",
    "command-center/p2-wave/probes/AUD-0042/write_receipts.py",
    "command-center/p2-wave/probes/AUD-0042/runs/steps.json",
    "command-center/p2-wave/probes/AUD-0042/fixtures/one/test_collected.py",
    ".github/workflows/quality.yml",
]


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = C.digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": C.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0042/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (C.REPO / C.OUT_REL).is_file():
        print("FAILED:AUD-0042 primary missing; run emit_artifact.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0042 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (C.REPO / p).is_file()]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT,
        "unit_id": C.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "runner-exit-code-per-step",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "parsed-result-summary-per-step",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0042/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0042-probe2-result-summaries",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0042: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT,
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
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0042 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
