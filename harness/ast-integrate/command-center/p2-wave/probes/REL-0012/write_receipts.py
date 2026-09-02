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
OUT = "command-center/receipts/REL-0012.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0012/probe1_tamper_and_untampered.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/REL-0012/probe2_commit_unsigned_schema.py"
)
SUPPORTING = [
    "command-center/schema/supply-chain-receipt.schema.json",
    "command-center/p2-wave/probes/REL-0012/common.py",
    "command-center/p2-wave/probes/REL-0012/engine.py",
    "command-center/p2-wave/probes/REL-0012/verify.py",
    "command-center/p2-wave/probes/REL-0012/emit_receipt.py",
    "command-center/p2-wave/probes/REL-0012/schema_local.py",
    "command-center/p2-wave/probes/REL-0012/probe1_tamper_and_untampered.py",
    "command-center/p2-wave/probes/REL-0012/probe2_commit_unsigned_schema.py",
    "command-center/p2-wave/probes/REL-0012/fixtures/RELEASE-NOTES.md",
    "command-center/p2-wave/probes/REL-0012/generated/artifact.zip",
    "command-center/p2-wave/probes/REL-0012/generated/provenance.json",
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
        "unit_id": "REL-0012",
        "receipt_path": "command-center/p2-wave/probes/REL-0012/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    emit = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/REL-0012/emit_receipt.py"
    )
    ce, te = run_probe(emit)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-2000:])
        return 1
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
        "id": "REL-0012",
        "unit_id": "REL-0012",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:REL-0012",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/supply-chain-receipt.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/REL-0012/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "REL-0012-probe2-independent-commit-unsigned-schema",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for REL-0012: live named probes exit 0, supply-chain receipt "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No key created, used, or rotated."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "REL-0012",
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
    print("SUCCESS:REL-0012 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
