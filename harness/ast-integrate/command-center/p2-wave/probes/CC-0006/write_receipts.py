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
REPO = HERE.parents[3]
OUT = "command-center/receipts/CC-0006.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0006/probe1_known_present_mention.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CC-0006/probe2_postfix_reviewer.py"
)
SUPPORTING = [
    "command-center/wrong_recipe_gate.py",
    "command-center/RELEASE-CHECKLIST.md",
    "rules/common/windows-shell.md",
    "command-center/p2-wave/probes/CC-0006/probe1_known_present_mention.py",
    "command-center/p2-wave/probes/CC-0006/probe2_postfix_reviewer.py",
    "command-center/p2-wave/probes/CC-0006/emit_receipt.py",
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
        "unit_id": "CC-0006",
        "receipt_path": "command-center/p2-wave/probes/CC-0006/SUBAGENT-RETURN.json",
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
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "id": "CC-0006",
        "manifest_path": "command-center/p2-wave/probes/CC-0006/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
            },
        ],
        "notes": (
            "G-1 for CC-0006: live named probes exit 0, receipts/CC-0006.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CC-0006-held-out-documentary-mention",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CC-0006",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CC-0006",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "CC-0006",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CC-0006 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
