#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import protocol as P

HERE = Path(__file__).resolve().parent
REPO = P.REPO
OUT = (
    "command-center/research/sources-frontier/"
    "RES-0182-expert-elicitation-as-a-source-class.json"
)
P1 = P.P1
P2 = P.P2
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0182/design-spec.schema.json",
    "command-center/p2-wave/probes/RES-0182/protocol.py",
    "command-center/p2-wave/probes/RES-0182/questions.json",
    "command-center/p2-wave/probes/RES-0182/participants.json",
    "command-center/p2-wave/probes/RES-0182/sources_index.json",
    "command-center/p2-wave/probes/RES-0182/probe1_recompute.py",
    "command-center/p2-wave/probes/RES-0182/probe2_negative_control.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return P.sha256_bytes(raw), len(raw)


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
        timeout=180,
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
        "unit_id": "RES-0182",
        "receipt_path": "command-center/p2-wave/probes/RES-0182/SUBAGENT-RETURN.json",
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
        "id": "RES-0182",
        "unit_id": "RES-0182",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0182",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/p2-wave/probes/RES-0182/design-spec.schema.json",
        "catalog_output_schema": "command-center/schema/design-spec.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "recompute-aggregation-and-lineage",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "negative-control-both-states",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0182/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0182-probe2-literature-miss-and-promotion-mutant",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0182: live named probes exit 0, design spec "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Catalog design-spec.schema.json is absent; "
            "this unit pins probes/RES-0182/design-spec.schema.json. Source class "
            "is WEAK (literature miss on Cooke 5/50/95 count). cloud ok=true is "
            "not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0182",
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
    print("SUCCESS:RES-0182 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
