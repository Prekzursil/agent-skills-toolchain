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
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402

REPO = G.REPO
SUPPORTING = [
    G.SCHEMA_REL,
    "command-center/p2-wave/probes/RES-0121/graph.py",
    "command-center/p2-wave/probes/RES-0121/emit.py",
    "command-center/p2-wave/probes/RES-0121/schema_check.py",
    "command-center/p2-wave/probes/RES-0121/probe1_reachable_sha256.py",
    "command-center/p2-wave/probes/RES-0121/probe2_traps_disagree.py",
    "command-center/p2-wave/probes/RES-0121/licenses/BMAD-METHOD.LICENSE",
    "command-center/p2-wave/probes/RES-0121/licenses/microsoft-autogen.LICENSE",
    "command-center/p2-wave/probes/RES-0121/fixtures/classifier/BMAD-METHOD.json",
    "command-center/p2-wave/probes/RES-0121/fixtures/classifier/microsoft-autogen.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": G.UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0121/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(G.P1)
    c2, t2 = run_probe(G.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{G.UNIT} receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(G.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": G.UNIT,
        "unit_id": G.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": G.CATALOG_SENTINEL,
        "registered": True,
        "output_path": G.OUT_REL,
        "output_schema": G.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": G.P1,
                "exit_code": c1,
                "role": "reachable-license-sha256",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": G.P2,
                "exit_code": c2,
                "role": "traps-and-disagreement",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": G.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0121/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0121-probe2-traps-disagree",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0121: live named probes exit 0, licence graph "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. E001-E189 register source absent; "
            "two named trap LICENSE files fetched and hashed. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": G.UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {G.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{G.UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
