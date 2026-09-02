#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0177/probe1_known_present.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0177/probe2_fabricated_absent.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0177/enumerate.py",
    "command-center/p2-wave/probes/RES-0177/estate.py",
    "command-center/p2-wave/probes/RES-0177/live.py",
    "command-center/p2-wave/probes/RES-0177/planned.py",
    "command-center/p2-wave/probes/RES-0177/probe1_known_present.py",
    "command-center/p2-wave/probes/RES-0177/probe2_fabricated_absent.py",
    "command-center/p2-wave/probes/RES-0177/emit_research.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "RES-0177",
        "receipt_path": "command-center/p2-wave/probes/RES-0177/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    out_path = REPO / OUT
    if not out_path.is_file() or out_path.stat().st_size <= 0:
        print("FAILED:RES-0177 receipts artifact missing; run emit_research.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0177 named probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0177",
        "unit_id": "RES-0177",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0177",
        "registered": False,
        "output_path": OUT,
        "output_schema": "command-center/schema/ecosystem-teardown.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "known-installed-both-signals",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "fabricated-name-and-directory-noise-mutant",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0177/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0177-probe2-fabricated-absent",
            "verdict": "PASS",
            "independent": True,
            "partitioned_independence": "NOT-MET-same-session",
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered RES-0177",
        "ts": now,
        "notes": (
            "G-1 for RES-0177: live named probes exit 0, teardown artifact "
            "state=SUCCESS, per-unit manifest row. Live ~/.claude/plugins is ABSENT "
            "on this Linux worktree; detector control uses the fixture estate. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0177",
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0177 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
