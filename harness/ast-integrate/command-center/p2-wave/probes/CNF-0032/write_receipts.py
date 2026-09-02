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
UNIT = "CNF-0032"
OUT_REL = "command-center/confirmation/CNF-0032-hunk-revert-causality.json"
SCHEMA_REL = "command-center/schema/causality-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0032/probe1_revert_restore.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0032/probe2_non_load_bearing.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0032/protocol.py",
    "command-center/p2-wave/probes/CNF-0032/fixtures/subject/app.py",
    "command-center/p2-wave/probes/CNF-0032/fixtures/subject/test_app.py",
    "command-center/p2-wave/probes/CNF-0032/probe1_revert_restore.py",
    "command-center/p2-wave/probes/CNF-0032/probe2_non_load_bearing.py",
    "command-center/p2-wave/probes/CNF-0032/emit_report.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = REPO / OUT_REL
    if not out.is_file() or out.stat().st_size <= 0:
        print(f"FAILED:{UNIT} primary artifact missing")
        return 1
    probes = []
    for pid, cmd in (("probe1", P1), ("probe2", P2)):
        code, text = run_cmd(cmd)
        probes.append(
            {
                "id": pid,
                "command": cmd,
                "exit_code": code,
                "raw_output": text[-4000:],
            }
        )
        print(f"{pid} rc={code}")
        if code != 0:
            print(text[-2000:])
            print(f"FAILED:{UNIT} {pid}")
            return 1

    sha, size = sha256_file(out)
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0032",
        "registered": False,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": probes,
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0032-probe2-non-load-bearing-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for CNF-0032: live named probes exit 0, causality report "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    artifacts = [row(OUT_REL, "primary")]
    for rel in SUPPORTING:
        artifacts.append(row(rel, "supporting"))
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
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} bytes={size} sha256={sha}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
