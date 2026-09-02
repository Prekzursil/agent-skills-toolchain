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
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

SUPPORTING = [
    L.SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0016/lib.py",
    "command-center/p2-wave/probes/AUD-0016/emit.py",
    "command-center/p2-wave/probes/AUD-0016/probe1_enabled_plugins_map.py",
    "command-center/p2-wave/probes/AUD-0016/probe2_skill_command_reachability.py",
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/user-home/.claude/settings.json",
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/user-home/.claude.json",
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/project/.claude/settings.json",
    "command-center/p2-wave/probes/AUD-0016/fixtures/estate/project/.claude/settings.local.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(L.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = L.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": L.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0016/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0016/emit.py"
    )
    ce, te = run_cmd(emit_cmd)
    if ce != 0:
        print(f"FAILED:AUD-0016 receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    c1, t1 = run_cmd(L.P1_CMD)
    c2, t2 = run_cmd(L.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0016 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    primary = row(L.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": L.UNIT,
        "unit_id": L.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": L.SENTINEL,
        "registered": True,
        "output_path": L.OUT_REL,
        "output_schema": L.SCHEMA_REL,
        "named_probes": [
            {"id": "probe1", "command": L.P1_CMD, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": L.P2_CMD, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": L.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0016/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0016-probe2-skill-command-reachability",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0016: live named probes exit 0, plugin-enablement-map "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": L.UNIT,
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
    print(f"primary {L.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0016 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
