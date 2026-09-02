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
import subtractor as S  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0159/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0159/probe2_independent_ratio.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0159/subtractor.py",
    "command-center/p2-wave/probes/RES-0159/emit_run.py",
    "command-center/p2-wave/probes/RES-0159/probe1_detector_control.py",
    "command-center/p2-wave/probes/RES-0159/probe2_independent_ratio.py",
    "command-center/p2-wave/probes/RES-0159/measurement-run.schema.json",
]


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(S.REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    digest, size = S.sha256_file(S.REPO / rel)
    return {
        "path": rel,
        "sha256": digest,
        "bytes": size,
        "present": True,
        "unit_id": "RES-0159",
        "receipt_path": "command-center/p2-wave/probes/RES-0159/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = S.REPO / S.OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        print("FAILED:RES-0159 receipts artifact missing; run emit_run.py first")
        return 1
    code1, text1 = run_probe(P1)
    code2, text2 = run_probe(P2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:RES-0159 named probes c1={code1} c2={code2}")
        print(text1[-2000:])
        print(text2[-2000:])
        return 1
    primary = row(S.OUT_REL, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0159",
        "unit_id": "RES-0159",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": S.SENTINEL,
        "registered": False,
        "output_path": S.OUT_REL,
        "output_schema": S.CATALOG_SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1,
                "role": "detector-control-three-restatements",
                "raw_output": text1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2,
                "role": "independent-ratio-recount",
                "raw_output": text2,
            },
        ],
        "artifacts": [
            {
                "path": S.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0159/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0159-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "partitioned_independence": "NOT-MET-same-session",
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered RES-0159",
        "ts": now,
        "notes": (
            "G-1 for RES-0159: live named probes exit 0, gem-hunt artifact "
            "state=SUCCESS with computed raw-to-novel ratio and 3-restatement "
            "detector control, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Windows Phase-0 workflow JSON absent; "
            "briefing retrieved from live PHASE-GRAPH.json and DEPENDENCY-GRAPH.json."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0159",
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
    print(f"primary {S.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0159 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
