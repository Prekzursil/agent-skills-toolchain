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
OUT = "command-center/synthesis/SYN-0009.raw-source-control.json"
SCHEMA = "command-center/schema/synthesis-candidate.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0009/probe1_denylist.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0009/probe2_no_sibling.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/SYN-0009/denylist.py",
    "command-center/p2-wave/probes/SYN-0009/inventory.py",
    "command-center/p2-wave/probes/SYN-0009/synthesizer.py",
    "command-center/p2-wave/probes/SYN-0009/reviewer.py",
    "command-center/p2-wave/probes/SYN-0009/emit_artifact.py",
    "command-center/p2-wave/probes/SYN-0009/schema_local.py",
    "command-center/p2-wave/probes/SYN-0009/probe1_denylist.py",
    "command-center/p2-wave/probes/SYN-0009/probe2_no_sibling.py",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/raw/transcript.json",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/raw/test-output.txt",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/raw/source.py",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/raw/notes.txt",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/digest/PHASE-DIGEST.md",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/digest/SUMMARY-report.json",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/narrative/receipt-narrative.md",
    "command-center/p2-wave/probes/SYN-0009/fixtures/corpus/sibling/SYN-0008.candidate-syntheses.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "unit_id": "SYN-0009",
        "receipt_path": "command-center/p2-wave/probes/SYN-0009/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    missing = [p for p in [OUT] + SUPPORTING if not (REPO / p).is_file()]
    if missing:
        print(f"FAILED:receipts missing {missing}")
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "SYN-0009",
        "unit_id": "SYN-0009",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0009",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "deny-list-known-present",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "no-sibling-independent-reviewer",
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
        "manifest_path": "command-center/p2-wave/probes/SYN-0009/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0009-probe2-independent-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0009: live named probes exit 0, raw-source-control "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Phase 10-13 production outputs ABSENT; "
            "controls proven on the fixture corpus. SYN-0008 unread is DENIED."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "SYN-0009",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"wrote return+manifest primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0009 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
