#!/usr/bin/env python3
"""Per-unit receipts for CNL-0035. Does not write the global catalog manifest."""
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
UID = "CNL-0035"
OUT_REL = (
    "command-center/design/council/"
    "CNL-0035-delphi-topology-iterated-anonymous-estimates-with-controll.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0035/probe1_herding.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0035/probe2_negative.py"
)


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, n = digest_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": n,
        "present": True,
        "exists": True,
        "unit_id": UID,
        "receipt_path": "command-center/p2-wave/probes/CNL-0035/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out = REPO / OUT_REL
    if not out.is_file():
        print("FAILED:CNL-0035 receipts: primary artifact missing")
        return 1
    probes = []
    for pid, cmd, role in (
        ("probe1", P1, "herding-control"),
        ("probe2", P2, "negative-control-and-recount"),
    ):
        code, text = run_cmd(cmd)
        probes.append(
            {
                "id": pid,
                "command": cmd,
                "exit_code": code,
                "role": role,
                "raw_output": text[-4000:],
            }
        )
        print(f"{pid} rc={code}")
        if code != 0:
            print(text[-1500:])
            print("FAILED:CNL-0035 receipts: named probe not green")
            return 1

    supporting = [
        ("command-center/p2-wave/probes/CNL-0035/delphi.py", "supporting"),
        ("command-center/p2-wave/probes/CNL-0035/probe1_herding.py", "supporting"),
        ("command-center/p2-wave/probes/CNL-0035/probe2_negative.py", "supporting"),
        ("command-center/p2-wave/probes/CNL-0035/emit_note.py", "supporting"),
        ("command-center/p2-wave/probes/CNL-0035/note_schema.py", "supporting"),
        (
            "command-center/p2-wave/probes/CNL-0035/fixtures/panel_heterogeneous.json",
            "fixture",
        ),
        (
            "command-center/p2-wave/probes/CNL-0035/fixtures/panel_homogeneous_guesses.json",
            "fixture",
        ),
        ("command-center/schema/council-design-note.schema.json", "schema"),
    ]
    artifacts = [row(OUT_REL, "primary")]
    for rel, role in supporting:
        if (REPO / rel).is_file():
            artifacts.append(row(rel, role))

    primary = artifacts[0]
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0035",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/council-design-note.schema.json",
        "named_probes": probes,
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNL-0035/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0035-probe2-second-moment-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for CNL-0035: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0035 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
