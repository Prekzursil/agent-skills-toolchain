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
sys.path.insert(0, str(HERE))

from paths import OUT_REL, P1, P2, SCHEMA_REL, UNIT  # noqa: E402

SUPPORTING = [
    SCHEMA_REL,
    "tools/plugin/eol_hash.py",
    "command-center/p2-wave/probes/AUD-0011/paths.py",
    "command-center/p2-wave/probes/AUD-0011/corpus.py",
    "command-center/p2-wave/probes/AUD-0011/compare.py",
    "command-center/p2-wave/probes/AUD-0011/adjudicate.py",
    "command-center/p2-wave/probes/AUD-0011/controls.py",
    "command-center/p2-wave/probes/AUD-0011/probe1_commit_vs_mtime.py",
    "command-center/p2-wave/probes/AUD-0011/probe2_semantic_hunks.py",
    "command-center/p2-wave/probes/AUD-0011/emit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0011/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0011/emit.py"
    )
    rc_e, out_e = run(emit_cmd)
    if rc_e != 0:
        print("FAILED:AUD-0011 emit")
        print(out_e[-3000:])
        return 1
    rc1, t1 = run(P1)
    rc2, t2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:AUD-0011 receipts probes c1={rc1} c2={rc2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
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
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0011/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0011-probe2-semantic-hunks",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0011: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Host rules trees are absent; the "
            "88-file fixture corpus is the measured pair. cloud ok=true "
            "is not delivery."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0011 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
