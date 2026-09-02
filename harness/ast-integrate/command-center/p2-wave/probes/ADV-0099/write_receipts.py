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
OUT = "command-center/adversarial/ADV-0099-hallucinated-expertise-in-selection.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0099/probe1_evidentiary_basis.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0099/probe2_known_answer_calibration.py"
)
SUPPORTING = [
    "command-center/schema/council-pathology-sim.schema.json",
    "tools/council/vote/weights.py",
    "command-center/p2-wave/probes/ADV-0099/audit.py",
    "command-center/p2-wave/probes/ADV-0099/quiz.py",
    "command-center/p2-wave/probes/ADV-0099/weights_gate.py",
    "command-center/p2-wave/probes/ADV-0099/probe1_evidentiary_basis.py",
    "command-center/p2-wave/probes/ADV-0099/probe2_known_answer_calibration.py",
    "command-center/p2-wave/probes/ADV-0099/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0099/fixtures/quiz.json",
    "command-center/p2-wave/probes/ADV-0099/fixtures/councils.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(os.environ)
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
        "unit_id": "ADV-0099",
        "receipt_path": "command-center/p2-wave/probes/ADV-0099/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [sys.executable, "-B", str(HERE / "emit_artifact.py")],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print("FAILED:ADV-0099 emit_artifact")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
    print((emit.stdout or "").strip())
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0099",
        "unit_id": "ADV-0099",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0099",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-pathology-sim.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0099/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0099-probe2-known-answer-calibration",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0099: live named probes exit 0, hallucinated-expertise "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not implement select_expertise.py."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0099",
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
    print("SUCCESS:ADV-0099 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
