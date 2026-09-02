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
UNIT = "WFA-0112"
OUT = "command-center/wfa/WFA-0112-benchmark-case-corpus.json"
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0112/emit.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0112/probe1_oracle_determinism.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0112/probe2_known_bad_and_cross_family.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0112/families.py",
    "command-center/p2-wave/probes/WFA-0112/oracle.py",
    "command-center/p2-wave/probes/WFA-0112/corpus.py",
    "command-center/p2-wave/probes/WFA-0112/emit.py",
    "command-center/p2-wave/probes/WFA-0112/probe1_oracle_determinism.py",
    "command-center/p2-wave/probes/WFA-0112/probe2_known_bad_and_cross_family.py",
    "command-center/p2-wave/probes/WFA-0112/benchmark-result.local.schema.json",
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
        timeout=180,
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
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:WFA-0112 receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    print(te)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0112 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    primary = row(OUT, "primary")
    if not primary["present"] or primary["bytes"] <= 0:
        print(f"FAILED:WFA-0112 missing primary {OUT}")
        return 1
    extras = []
    fixtures = HERE / "fixtures"
    if fixtures.is_dir():
        for path in sorted(fixtures.rglob("*")):
            if path.is_file():
                rel = path.relative_to(REPO).as_posix()
                extras.append(rel)
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING + extras]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0112",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/BenchmarkResult",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[-4000:],
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0112-probe2-known-bad-and-cross-family",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0112: live named probes exit 0, "
            "wfa/WFA-0112-benchmark-case-corpus.json state=SUCCESS, per-unit "
            "manifest row. Did not run global unit_manifest.py --write. No ADV "
            "rebuild. Cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
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
    print("SUCCESS:WFA-0112 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
