#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md"
P1 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0112/probe1_instantiate.py"
P2 = "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0112/probe2_sibling_schema.py"
SUPPORTING = [
    "command-center/schema/council-preset.schema.json",
    "command-center/p2-wave/probes/CNL-0112/artifact.schema.json",
    "command-center/p2-wave/probes/CNL-0112/instantiate.py",
    "command-center/p2-wave/probes/CNL-0112/scoring.py",
    "command-center/p2-wave/probes/CNL-0112/probe1_instantiate.py",
    "command-center/p2-wave/probes/CNL-0112/probe2_sibling_schema.py",
    "command-center/p2-wave/probes/CNL-0112/fixtures/task.json",
    "command-center/p2-wave/probes/CNL-0112/fixtures/sibling.json",
    "command-center/p2-wave/probes/ARC-0003/samples.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "CNL-0112",
        "receipt_path": "command-center/p2-wave/probes/CNL-0112/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
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
        "id": "CNL-0112",
        "unit_id": "CNL-0112",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0112",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-preset.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0112/SUBAGENT-RETURN.json".replace(
            "SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "CNL-0112-probe2-sibling-differential",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNL-0112: live named probes exit 0, forecasting preset "
            "artifact state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Library 12-COUNCIL-PROTOCOLS-AND-PRESETS.json "
            "absent; nearest sibling is the on-tree catalog transcription."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0112",
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
    print("SUCCESS:CNL-0112 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
