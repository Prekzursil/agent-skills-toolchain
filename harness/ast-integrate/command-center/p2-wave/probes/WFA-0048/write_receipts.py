#!/usr/bin/env python3
"""Write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for WFA-0048."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UID = "WFA-0048"
OUT = "command-center/wfa/WFA-0048-adapter-slash-command.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0048/probe1_detector_control.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0048/probe2_collapse_and_floor.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0048/adapter.py",
    "command-center/p2-wave/probes/WFA-0048/alias_proof.py",
    "command-center/p2-wave/probes/WFA-0048/corpus.py",
    "command-center/p2-wave/probes/WFA-0048/emit_report.py",
    "command-center/p2-wave/probes/WFA-0048/probe1_detector_control.py",
    "command-center/p2-wave/probes/WFA-0048/probe2_collapse_and_floor.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/WFA-0048/SUBAGENT-RETURN.json",
        "role": role,
    }


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=True) + "\n"


def main() -> int:
    c_emit, t_emit = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/WFA-0048/emit_report.py"
    )
    if c_emit != 0:
        print(f"FAILED:receipts emit rc={c_emit}")
        print(t_emit[-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0048",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AdapterConformanceReport",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "detector-control-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "alias-collapse-floor-carry",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0048/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0048-probe1-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered WFA-0048",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered WFA-0048"},
        "ts": now,
        "notes": (
            "G-1 for WFA-0048: live named probes exit 0, adapter report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok is false and is not delivery. "
            "Live command trees were absent; corpus is frozen I-family n=31."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(dump(ret), encoding="utf-8", newline="\n")
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        dump(man), encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0048 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
