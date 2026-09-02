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
    "command-center/research/gem-hunt/"
    "RES-0158-transfer-structured-analytic-techniques.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0158/probe1_source_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0158/probe2_protocol_crosscheck.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0158/lib.py",
    "command-center/p2-wave/probes/RES-0158/engine.py",
    "command-center/p2-wave/probes/RES-0158/emit_artifact.py",
    "command-center/p2-wave/probes/RES-0158/probe1_source_coverage.py",
    "command-center/p2-wave/probes/RES-0158/probe2_protocol_crosscheck.py",
    "command-center/p2-wave/probes/RES-0158/artifact.schema.json",
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
        "unit_id": "RES-0158",
        "receipt_path": "command-center/p2-wave/probes/RES-0158/SUBAGENT-RETURN.json",
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
        "id": "RES-0158",
        "unit_id": "RES-0158",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0158",
        "output_path": OUT,
        "output_schema": "command-center/schema/gem-candidate.schema.json",
        "cloud_ok": False,
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/RES-0158/UNIT-ARTIFACT-MANIFEST.json",
        "ts": now,
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0158-probe2-protocol-crosscheck",
            "verdict": "PASS",
            "defaults_to": "REFUTED",
        },
        "named_probes": [
            {
                "id": "probe1",
                "role": "source-coverage-two-rails-ach-critique",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1[-4000:],
            },
            {
                "id": "probe2",
                "role": "protocol-crosscheck-both-states",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2[-4000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "role": "primary",
                "bytes": primary["bytes"],
                "sha256": primary["sha256"],
                "exists": True,
            }
        ],
        "notes": (
            "G-1 for RES-0158: live named probes exit 0, gem-hunt artifact "
            "state=SUCCESS (not BLOCKED), per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Did not rebuild ADV. ICD-203 is "
            "recorded as not-a-protocol-blueprint; ACH incomplete-set critique "
            "is recorded, not pitched away."
        ),
    }
    man = {
        "schema_version": 1,
        "unit_id": "RES-0158",
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "verified_on_disk": True,
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote receipts artifacts={len(artifacts)} primary_sha={primary['sha256']}")
    print("SUCCESS:RES-0158 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
