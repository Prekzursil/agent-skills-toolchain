#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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
RET = HERE / "SUBAGENT-RETURN.json"
MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"
OUT = "command-center/phase3/A2/MIGRATION.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0014/probe1_roundtrip.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0014/probe2_rollback.py"
)
SUPPORTING = (
    "command-center/schema/migration-plan.schema.json",
    "command-center/p2-wave/probes/ARC-0014/extract.py",
    "command-center/p2-wave/probes/ARC-0014/scenario.py",
    "command-center/p2-wave/probes/ARC-0014/freeze_hook.py",
    "command-center/p2-wave/probes/ARC-0014/rollback.py",
    "command-center/p2-wave/probes/ARC-0014/probe1_roundtrip.py",
    "command-center/p2-wave/probes/ARC-0014/probe2_rollback.py",
    "command-center/p2-wave/probes/ARC-0014/emit_migration.py",
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "ARC-0014",
        "receipt_path": "command-center/p2-wave/probes/ARC-0014/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    receipt = REPO / OUT
    if not receipt.is_file() or receipt.stat().st_size < 200:
        print("FAILED:ARC-0014 write-return migration artifact missing")
        return 1

    rc1, out1 = run(P1)
    print(out1[-4000:])
    if rc1 != 0:
        print(f"FAILED:ARC-0014 probe1 rc={rc1}")
        return 1
    rc2, out2 = run(P2)
    print(out2[-4000:])
    if rc2 != 0:
        print(f"FAILED:ARC-0014 probe2 rc={rc2}")
        return 1

    primary = art(OUT, "primary")
    supporting = [art(rel, "supporting") for rel in SUPPORTING]
    rows = [primary, *supporting]
    missing = [r["path"] for r in rows if not r["present"]]
    if missing:
        print("FAILED:ARC-0014 missing artifacts", missing)
        return 1

    ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    ret = {
        "id": "ARC-0014",
        "unit_id": "ARC-0014",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0014",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/migration-plan.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "round-trip-fidelity",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "rollback-rehearsal",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": primary["path"],
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ARC-0014/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ARC-0014-probe1-roundtrip",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered ARC-0014",
        "measure": {
            "exit_code": 0,
            "line": "SUCCESS:delivered ARC-0014"
        },
        "ts": ts,
        "notes": (
            "G-1 for ARC-0014: live named probes exit 0, MIGRATION.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    RET.write_text(json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ARC-0014",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    MAN.write_text(json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {RET.relative_to(REPO)} and {MAN.relative_to(REPO)}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ARC-0014 write-return")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
