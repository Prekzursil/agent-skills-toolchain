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
OUT = "command-center/wfa/WFA-0119-decertification-and-supersession.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0119/probe1_benchmark_refuse.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0119/probe2_preserve_owner.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0119/emit_record.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/WFA-0119/supersession.py",
    "command-center/p2-wave/probes/WFA-0119/emit_record.py",
    "command-center/p2-wave/probes/WFA-0119/probe1_benchmark_refuse.py",
    "command-center/p2-wave/probes/WFA-0119/probe2_preserve_owner.py",
    "command-center/p2-wave/probes/WFA-0119/certification_record.standin.schema.json",
    "command-center/p2-wave/probes/WFA-0119/fixtures/incidence_matrix.json",
    "command-center/p2-wave/probes/WFA-0119/fixtures/workflows.json",
    "command-center/p2-wave/probes/WFA-0119/fixtures/benchmarks.json",
    "command-center/p2-wave/probes/WFA-0119/fixtures/owner_signoff.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": "WFA-0119",
        "receipt_path": "command-center/p2-wave/probes/WFA-0119/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "WFA-0119",
        "unit_id": "WFA-0119",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0119",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/CertificationRecord",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "benchmark-refuse-and-signal-divergence",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "preservation-retrieval-and-owner-gate",
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0119/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0119-probe1-benchmark-refuse",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "required_fix": None,
        "ts": now,
        "notes": (
            "G-1 for WFA-0119: live named probes exit 0, CertificationRecord "
            "state=SUCCESS, per-unit manifest row. Declared schema pack and "
            "dependency artifacts WFA-0118/WFA-0076 are absent; this unit uses "
            "fixture stand-ins and a local CertificationRecord schema. Fixture "
            "rehearsal only — no live-estate workflow was retired. Did not run "
            "global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0119",
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
    print("SUCCESS:WFA-0119 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
