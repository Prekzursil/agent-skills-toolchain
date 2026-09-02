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
OUT = "command-center/adversarial/ADV-0075-filename-path-unicode-injection.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0075/probe1_enumerate_render.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0075/probe2_tool_resolve.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0075/emit_result.py"
)
SUPPORTING = [
    "command-center/schema/injection-corpus-result.schema.json",
    "command-center/p2-wave/probes/ADV-0075/fixtures.py",
    "command-center/p2-wave/probes/ADV-0075/rendering.py",
    "command-center/p2-wave/probes/ADV-0075/tool_layer.py",
    "command-center/p2-wave/probes/ADV-0075/checks.py",
    "command-center/p2-wave/probes/ADV-0075/probe1_enumerate_render.py",
    "command-center/p2-wave/probes/ADV-0075/probe2_tool_resolve.py",
    "command-center/p2-wave/probes/ADV-0075/emit_result.py",
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
        "unit_id": "ADV-0075",
        "receipt_path": "command-center/p2-wave/probes/ADV-0075/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc_e, out_e = run_cmd(EMIT)
    if rc_e != 0:
        print(f"FAILED:receipts emit rc={rc_e}")
        print(out_e[-2000:])
        return 1
    print(out_e)
    rc1, t1 = run_cmd(P1)
    rc2, t2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:receipts probes rc1={rc1} rc2={rc2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0075",
        "unit_id": "ADV-0075",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0075",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/injection-corpus-result.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0075/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0075-probe2-os-resolve",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0075: live named probes exit 0, filename-path-unicode "
            "injection artifact state=SUCCESS, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. No ADV rebuild. Measured "
            "line-oriented listing, RTL visual render, cat argv, inodes, and "
            "reconcile_delivery._fold on this Linux worktree."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0075",
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
    print("SUCCESS:ADV-0075 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
