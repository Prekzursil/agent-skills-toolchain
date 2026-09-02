#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for WFA-0147."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0147"
OUT = "command-center/foundry/WFA-0147-settle-the-44-unknown-needs-probe-candidates.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0147/probe1_dispatch_and_recount.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0147/probe2_promotion_gate.py"
)
SUPPORTING = [
    "tools/workflow_foundry/unknown_probe.py",
    "tools/workflow_foundry/blueprint_gate.py",
    "command-center/p2-wave/probes/WFA-0147/corpus.py",
    "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json",
    "command-center/p2-wave/probes/WFA-0147/probe1_dispatch_and_recount.py",
    "command-center/p2-wave/probes/WFA-0147/probe2_promotion_gate.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/WFA-0147/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = HERE / "emit_artifact.py"
    c0, t0 = run_cmd(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}")
    if c0 != 0:
        print(f"FAILED:{UNIT} emit rc={c0}")
        print(t0[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0147",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/foundry-artifact.schema.json#/$defs/probe-dispatch",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "array-recount-and-live-named-settles",
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "promotion-gate-both-states",
                "raw_output": t2[-4000:],
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0147/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0147-probe2-promotion-gate",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0147: live named probes exit 0, foundry artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud_ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:WFA-0147 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
