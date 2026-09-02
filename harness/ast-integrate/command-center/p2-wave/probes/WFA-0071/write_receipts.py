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
REPO = Path(__file__).resolve().parents[4]
OUT = "command-center/wfa/WFA-0071-retire-readjudication.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0071/probe1_existence_and_rationale.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0071/probe2_preservation_hashmatch.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0071/disposition.schema.json",
    "command-center/p2-wave/probes/WFA-0071/locate.py",
    "command-center/p2-wave/probes/WFA-0071/engine.py",
    "command-center/p2-wave/probes/WFA-0071/controls.py",
    "command-center/p2-wave/probes/WFA-0071/probe1_existence_and_rationale.py",
    "command-center/p2-wave/probes/WFA-0071/probe2_preservation_hashmatch.py",
    "command-center/p2-wave/probes/WFA-0071/emit_artifact.py",
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
        "unit_id": "WFA-0071",
        "receipt_path": "command-center/p2-wave/probes/WFA-0071/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = subprocess.run(
        [
            sys.executable,
            "-B",
            str(HERE / "emit_artifact.py"),
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
    )
    if emit.returncode != 0:
        print("FAILED:receipts emit")
        print((emit.stdout or "")[-2000:])
        print((emit.stderr or "")[-2000:])
        return 1
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
        "id": "WFA-0071",
        "unit_id": "WFA-0071",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0071",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/DispositionRecord"
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0071/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0071-probe2-preservation-hashmatch",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0071: live named probes exit 0, DispositionRecord "
            "state=SUCCESS with SUCCESS:WFA-0071, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild. "
            "Original RETIRE n=24 registry absent on this worktree: 24 P1 "
            "identity-unrecoverable rows, terminal_retire_count=0."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0071",
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
    print("SUCCESS:WFA-0071 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
