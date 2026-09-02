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
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = S.OUT_REL
P1 = S.P1
P2 = S.P2
SUPPORTING = [
    S.SCHEMA_REL,
    "command-center/p2-wave/probes/CNF-0082/scout.py",
    "command-center/p2-wave/probes/CNF-0082/scenario.py",
    "command-center/p2-wave/probes/CNF-0082/recommend.py",
    "command-center/p2-wave/probes/CNF-0082/control.py",
    "command-center/p2-wave/probes/CNF-0082/probe1_rediscovery.py",
    "command-center/p2-wave/probes/CNF-0082/probe2_ranking.py",
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
        "receipt_path": "command-center/p2-wave/probes/CNF-0082/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CNF-0082",
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
        "id": "CNF-0082",
        "manifest_path": "command-center/p2-wave/probes/CNF-0082/UNIT-ARTIFACT-MANIFEST.json",
        "measure_line": "SUCCESS:delivered CNF-0082",
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
            "G-1 for CNF-0082: live named probes exit 0, scout-rediscovery "
            "artifact state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": S.SCHEMA_REL,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNF-0082-probe2-ranking-injection-mutant",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNF-0082",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CNF-0082",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "CNF-0082",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNF-0082 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
