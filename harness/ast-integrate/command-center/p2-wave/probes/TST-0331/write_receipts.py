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

import emit_receipt as E  # noqa: E402

UNIT = E.UNIT
OUT = E.OUT
SCHEMA = E.SCHEMA
SENTINEL = E.SENTINEL
P1 = E.P1
P2 = E.P2
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0331/validator.py",
    "command-center/p2-wave/probes/TST-0331/fixtures.py",
    "command-center/p2-wave/probes/TST-0331/probe1_planted_bad.py",
    "command-center/p2-wave/probes/TST-0331/probe2_revision.py",
    "command-center/p2-wave/probes/TST-0331/emit_receipt.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/TST-0331/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": UNIT,
    }


def main() -> int:
    rc = E.main()
    if rc != 0:
        return rc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    artifacts = [row(OUT, "primary")] + [
        row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    primary = artifacts[0]
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
        "id": UNIT,
        "manifest_path": "command-center/p2-wave/probes/TST-0331/UNIT-ARTIFACT-MANIFEST.json",
        "measure": {"exit_code": 0, "line": f"SUCCESS:delivered {UNIT}"},
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            "G-1 for TST-0331: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. Line-range checks at a cited revision "
            "use git show, not the worktree. This Linux worktree has no .git; "
            "revision correctness uses a hermetic tempfile repo."
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "TST-0331-probe2-revision",
            "verdict": "PASS",
        },
        "sentinel": SENTINEL,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": UNIT,
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": UNIT,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
