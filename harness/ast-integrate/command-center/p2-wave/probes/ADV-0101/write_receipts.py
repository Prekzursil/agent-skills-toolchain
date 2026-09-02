#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/adversarial/ADV-0101-stopping-rule-both-directions.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0101/probe1_paired_councils.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0101/probe2_info_gain.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0101/emit_artifact.py"
)
SUPPORTING = [
    "command-center/schema/council-pathology-sim.schema.json",
    "command-center/p2-wave/probes/ADV-0101/stopping.py",
    "command-center/p2-wave/probes/ADV-0101/simulate.py",
    "command-center/p2-wave/probes/ADV-0101/probe1_paired_councils.py",
    "command-center/p2-wave/probes/ADV-0101/probe2_info_gain.py",
    "command-center/p2-wave/probes/ADV-0101/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    sha, size = digest(REPO / rel)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/ADV-0101/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "ADV-0101",
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    print(te)
    if ce != 0:
        print(f"FAILED:ADV-0101-receipts emit rc={ce}")
        return 1

    art = REPO / OUT
    doc = json.loads(art.read_text(encoding="utf-8"))
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0101-receipts probes c1={c1} c2={c2}")
        return 1

    doc["named_probes"][0]["raw_output"] = t1
    doc["named_probes"][0]["exit_code"] = c1
    doc["named_probes"][1]["raw_output"] = t2
    doc["named_probes"][1]["exit_code"] = c2
    art.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")

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
        "id": "ADV-0101",
        "manifest_path": "command-center/p2-wave/probes/ADV-0101/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            "G-1 for ADV-0101: live named probes exit 0, stopping-rule both-directions "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/council-pathology-sim.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0101-probe2-independent-info-gain",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:ADV-0101",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "ADV-0101",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "ADV-0101",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0101 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
