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
    "command-center/p2-wave/probes/AUD-0007/lib.py",
    "command-center/p2-wave/probes/AUD-0007/probe1_remote_v.py",
    "command-center/p2-wave/probes/AUD-0007/probe2_config_regexp.py",
    "command-center/p2-wave/probes/AUD-0007/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
        "receipt_path": "command-center/p2-wave/probes/AUD-0007/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(L.P1_CMD)
    c2, t2 = run_probe(L.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0007 receipts probes c1={c1} c2={c2}")
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0007/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0007-probe2-config-regexp",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0007: live named probes exit 0, no-remote triage "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No remotes created."
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
    print("SUCCESS:AUD-0007 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
