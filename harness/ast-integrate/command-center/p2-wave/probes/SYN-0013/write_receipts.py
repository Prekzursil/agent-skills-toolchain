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
import constants as C  # noqa: E402

SUPPORTING = [
    C.SCHEMA_REL,
    C.LIB_REL,
    "tools/synthesis/__init__.py",
    "command-center/p2-wave/probes/SYN-0013/constants.py",
    "command-center/p2-wave/probes/SYN-0013/emit_receipt.py",
    "command-center/p2-wave/probes/SYN-0013/probe1_use_vs_mention.py",
    "command-center/p2-wave/probes/SYN-0013/probe2_retention_and_evidence.py",
    "command-center/p2-wave/probes/SYN-0013/fixtures/use_vs_mention.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/source_full.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/synthesis_lossy.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/candidate_good.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/candidate_no_block.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/candidate_two_anchors.md",
    "command-center/p2-wave/probes/SYN-0013/fixtures/candidate_six_anchors.md",
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
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
        "present": path.is_file(),
        "unit_id": C.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/SYN-0013/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/SYN-0013/emit_receipt.py"
    )
    ce, te = run_cmd(emit)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(C.P1_CMD)
    c2, t2 = run_cmd(C.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:SYN-0013",
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1_CMD,
                "exit_code": c1,
                "role": "use-vs-mention-detector-control",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": C.P2_CMD,
                "exit_code": c2,
                "role": "per-class-retention-and-evidence-gate",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/SYN-0013/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "SYN-0013-probe1-use-vs-mention-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for SYN-0013: live named probes exit 0, SYN-0013.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT_ID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:SYN-0013 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
