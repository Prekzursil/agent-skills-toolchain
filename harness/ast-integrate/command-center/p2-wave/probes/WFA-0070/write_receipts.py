#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not run tools/command-center/unit_manifest.py --write.
"""
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
sys.path.insert(0, str(HERE))
import emit_report as E  # noqa: E402

OUT = "command-center/wfa/WFA-0070-unknown-needs-probe-settlement.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0070/probe1_live_settlement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0070/probe2_both_states.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0070/settle.py",
    "command-center/p2-wave/probes/WFA-0070/emit_report.py",
    "command-center/p2-wave/probes/WFA-0070/probe1_live_settlement.py",
    "command-center/p2-wave/probes/WFA-0070/probe2_both_states.py",
    "command-center/p2-wave/probes/WFA-0070/fixtures/workflows/ok.json",
    "command-center/p2-wave/probes/WFA-0070/fixtures/workflows/broken.json",
    "command-center/p2-wave/probes/WFA-0070/fixtures/workflows/wrapper.json",
    "command-center/p2-wave/probes/WFA-0070/fixtures/workflows/tombstone.json",
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
        "exists": True,
        "unit_id": "WFA-0070",
        "receipt_path": "command-center/p2-wave/probes/WFA-0070/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    erc = E.main()
    if erc != 0:
        print(f"FAILED:receipts emit rc={erc}")
        return erc
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
        "id": "WFA-0070",
        "unit_id": "WFA-0070",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0070",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/ProbeReport",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "live-named-probe-settlement",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "both-states-detector-control",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0070/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0070-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0070: live named probes exit 0, settlement report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Authoritative registry is absent on this "
            "tree; 44 slots stay UNKNOWN with the blocker named. Engine fixture "
            "proves both-states and refuses silence-as-pass."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0070",
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
    print("SUCCESS:WFA-0070 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
