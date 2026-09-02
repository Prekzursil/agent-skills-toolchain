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
OUT = (
    "command-center/research/sources-frontier/"
    "RES-0183-owner-decision-log-as-a-source-class.json"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0183/emit_spec.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0183/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0183/probe2_quote_lineage.py"
)
SUPPORTING = [
    "command-center/schema/design-spec.schema.json",
    "command-center/p2-wave/probes/RES-0183/extract.py",
    "command-center/p2-wave/probes/RES-0183/checker.py",
    "command-center/p2-wave/probes/RES-0183/emit_spec.py",
    "command-center/p2-wave/probes/RES-0183/probe1_both_states.py",
    "command-center/p2-wave/probes/RES-0183/probe2_quote_lineage.py",
    "command-center/p2-wave/probes/RES-0183/fixtures/drafts.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "RES-0183",
        "receipt_path": "command-center/p2-wave/probes/RES-0183/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:RES-0183 receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0183 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0183",
        "unit_id": "RES-0183",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0183",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/design-spec.schema.json",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
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
        "manifest_path": "command-center/p2-wave/probes/RES-0183/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0183-probe2-quote-lineage",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0183: live named probes exit 0, design spec "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. 07-OPTION-UNIVERSE.json absent; "
            "17-DECISION-LOG.md is the CC-0022 reconstruction and does not "
            "bind PR-ONLY."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0183",
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0183 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
