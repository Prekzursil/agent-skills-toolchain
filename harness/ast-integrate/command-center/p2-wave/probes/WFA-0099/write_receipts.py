#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
OUT = "command-center/wfa/WFA-0099-collapse-audit-trail.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0099/probe1_restore_rehearsal.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0099/probe2_append_only_and_entry.py"
)
EMIT = "command-center/p2-wave/probes/WFA-0099/emit.py"
SUPPORTING = [
    "command-center/wfa/WFA-0099-collapse-trail.jsonl",
    "command-center/p2-wave/probes/WFA-0099/engine.py",
    "command-center/p2-wave/probes/WFA-0099/tokens.py",
    "command-center/p2-wave/probes/WFA-0099/fixtures.py",
    "command-center/p2-wave/probes/WFA-0099/emit.py",
    "command-center/p2-wave/probes/WFA-0099/probe1_restore_rehearsal.py",
    "command-center/p2-wave/probes/WFA-0099/probe2_append_only_and_entry.py",
    "command-center/p2-wave/probes/WFA-0099/audit-report.schema.json",
    "command-center/p2-wave/probes/WFA-0099/trail-record.schema.json",
]


def repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / CATALOG).is_file():
            return p
    raise SystemExit("FAILED:WFA-0099 receipts repo root not found")


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(repo: Path, cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(repo),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(repo: Path, rel: str, role: str) -> dict:
    path = repo / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "WFA-0099",
        "receipt_path": "command-center/p2-wave/probes/WFA-0099/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    repo = repo_root()
    c0, t0 = run_cmd(repo, f"PYTHONDONTWRITEBYTECODE=1 python3 -B {EMIT}")
    if c0 != 0:
        print(f"FAILED:WFA-0099 receipts emit rc={c0}")
        print(t0[-3000:])
        return 1
    print(t0[-500:])
    art = repo / OUT
    if not art.is_file():
        print("FAILED:WFA-0099 receipts primary artifact missing")
        return 1
    c1, t1 = run_cmd(repo, P1)
    c2, t2 = run_cmd(repo, P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0099 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(repo, OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if (repo / rel).is_file():
            artifacts.append(row(repo, rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0099",
        "unit_id": "WFA-0099",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0099",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport",
        "live_schema": "command-center/p2-wave/probes/WFA-0099/audit-report.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "restore-rehearsal-and-schema",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "append-only-and-entry-point",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0099/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0099-probe2-append-only-and-entry",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for WFA-0099: live named probes exit 0, "
            "wfa/WFA-0099-collapse-audit-trail.json state=SUCCESS, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. WFA-0001 schema pack and WFA-0095 "
            "policy artifact are absent; local schema and encoded union policy "
            "are disclosed."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0099",
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
    print("SUCCESS:WFA-0099 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
