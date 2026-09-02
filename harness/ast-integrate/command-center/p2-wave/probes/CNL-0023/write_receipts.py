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
OUT = (
    "command-center/design/council/"
    "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0023/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0023/probe2_independent_recount.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json",
    "command-center/p2-wave/probes/CNL-0023/validator.py",
    "command-center/p2-wave/probes/CNL-0023/recount.py",
    "command-center/p2-wave/probes/CNL-0023/probe1_both_states.py",
    "command-center/p2-wave/probes/CNL-0023/probe2_independent_recount.py",
    "command-center/p2-wave/probes/CNL-0023/fixtures/known-good.json",
    "command-center/p2-wave/probes/CNL-0023/fixtures/planted-bad.json",
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
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/CNL-0023/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CNL-0023",
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
        "id": "CNL-0023",
        "manifest_path": "command-center/p2-wave/probes/CNL-0023/UNIT-ARTIFACT-MANIFEST.json",
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
            "G-1 for CNL-0023: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Unjustified non-equal weight is rejected "
            "at spec validation before the council runs."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/councilspec.v2.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNL-0023-probe2-independent-recount",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNL-0023",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CNL-0023",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "CNL-0023",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0023 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
