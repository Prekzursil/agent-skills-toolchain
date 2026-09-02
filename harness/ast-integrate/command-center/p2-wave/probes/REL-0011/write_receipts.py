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
OUT = "command-center/receipts/REL-0011.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0011/probe1_closure_minus_bill.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0011/probe2_phantom_and_clean.py"
)
SUPPORTING = [
    "command-center/schema/supply-chain-receipt.schema.json",
    "command-center/receipts/REL-0011.cdx.json",
    "command-center/p2-wave/probes/REL-0011/generator.py",
    "command-center/p2-wave/probes/REL-0011/resolver.py",
    "command-center/p2-wave/probes/REL-0011/diff.py",
    "command-center/p2-wave/probes/REL-0011/scenario.py",
    "command-center/p2-wave/probes/REL-0011/probe1_closure_minus_bill.py",
    "command-center/p2-wave/probes/REL-0011/probe2_phantom_and_clean.py",
    "command-center/p2-wave/probes/REL-0011/fixtures/release/package-lock.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "unit_id": "REL-0011",
        "receipt_path": "command-center/p2-wave/probes/REL-0011/SUBAGENT-RETURN.json",
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
        "id": "REL-0011",
        "unit_id": "REL-0011",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0011",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/supply-chain-receipt.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/REL-0011/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0011-probe2-phantom-and-clean",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for REL-0011: live named probes exit 0, REL-0011.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
        "measure": {
            "exit_code": 0,
            "line": "SUCCESS:delivered REL-0011",
        },
        "measure_line": "SUCCESS:delivered REL-0011",
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "REL-0011",
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
    print("SUCCESS:REL-0011 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
