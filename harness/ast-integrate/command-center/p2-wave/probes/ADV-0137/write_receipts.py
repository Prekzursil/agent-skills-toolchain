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
OUT = "command-center/adversarial/ADV-0137-premise-concentration.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0137/probe1_hygiene_and_plant.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0137/probe2_independent_counter.py"
)
SUPPORTING = [
    "command-center/schema/concentration-report.schema.json",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/p2-wave/probes/ADV-0137/counting_rule.py",
    "command-center/p2-wave/probes/ADV-0137/harvest_json.py",
    "command-center/p2-wave/probes/ADV-0137/harvest_scan.py",
    "command-center/p2-wave/probes/ADV-0137/rank.py",
    "command-center/p2-wave/probes/ADV-0137/rederive.py",
    "command-center/p2-wave/probes/ADV-0137/emit.py",
    "command-center/p2-wave/probes/ADV-0137/probe1_hygiene_and_plant.py",
    "command-center/p2-wave/probes/ADV-0137/probe2_independent_counter.py",
    "command-center/p2-wave/probes/ADV-0137/fixtures/fake-brief.md",
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
        "unit_id": "ADV-0137",
        "receipt_path": "command-center/p2-wave/probes/ADV-0137/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0137",
        "unit_id": "ADV-0137",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0137",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/concentration-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "context-hygiene-and-planted-disagreement",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "independent-histogram-counter",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0137/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0137-probe2-independent-counter",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the histogram with a string-aware scanner; "
                "probe 1 audits bundle hygiene. Did not run global "
                "unit_manifest.py --write."
            ),
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0137: live named probes exit 0, concentration report "
            "state=SUCCESS with catalog completion sentinel, per-unit manifest "
            "row. cloud ok=true is not delivery. No ADV rebuild circle."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0137",
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
    print("SUCCESS:ADV-0137 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
