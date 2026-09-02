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
OUT = (
    "command-center/design/council/"
    "CNL-0052-adversarial-attack-on-the-unique-idea-counter-count-gaming.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0052/probe1_execute_attack.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0052/probe2_reviewer_rerun.py"
)
SUPPORTING = [
    "command-center/schema/council-detector-spec.schema.json",
    "command-center/p2-wave/probes/CNL-0052/f01.py",
    "command-center/p2-wave/probes/CNL-0052/attack.py",
    "command-center/p2-wave/probes/CNL-0052/probe1_execute_attack.py",
    "command-center/p2-wave/probes/CNL-0052/probe2_reviewer_rerun.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
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
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/CNL-0052/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "CNL-0052",
    }


def main() -> int:
    emit = HERE / "emit.py"
    c0, t0 = run_probe(f"PYTHONDONTWRITEBYTECODE=1 python3 -B {emit.relative_to(REPO).as_posix()}")
    if c0 != 0:
        print(f"FAILED:receipts emit c0={c0}")
        print(t0[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
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
        "id": "CNL-0052",
        "manifest_path": "command-center/p2-wave/probes/CNL-0052/UNIT-ARTIFACT-MANIFEST.json",
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
            "G-1 for CNL-0052: live named probes exit 0, attack executed, "
            "F01 unique count reported as a number, named failure :11339 "
            "reproduced on naive equality, F01 survives, per-unit manifest "
            "row. Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/council-detector-spec.schema.json",
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "CNL-0052-probe2-connected-components",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:CNL-0052",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "CNL-0052",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "CNL-0052",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0052 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
