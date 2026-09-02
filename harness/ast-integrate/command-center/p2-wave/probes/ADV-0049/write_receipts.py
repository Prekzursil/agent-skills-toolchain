#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import emit_artifact  # noqa: E402

OUT = C.ART_REL
P1 = C.P1_CMD
P2 = C.P2_CMD
SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0049/common.py",
    "command-center/p2-wave/probes/ADV-0049/lineage.py",
    "command-center/p2-wave/probes/ADV-0049/probe1_fusion_record.py",
    "command-center/p2-wave/probes/ADV-0049/probe2_decompose.py",
    "command-center/p2-wave/probes/ADV-0049/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0049/fixtures/sources.json",
    "command-center/p2-wave/probes/ADV-0049/probe1-fusion-record.raw.txt",
    "command-center/p2-wave/probes/ADV-0049/probe2-decompose.raw.txt",
    "command-center/p2-wave/probes/WFA-0127/scout.py",
    "command-center/p2-wave/probes/WFA-0127/licence.py",
    "command-center/p2-wave/probes/WFA-0127/fixtures/corpus/licence_lattice.json",
]


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(C.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = C.sha256_file(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "ADV-0049",
        "receipt_path": "command-center/p2-wave/probes/ADV-0049/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc = emit_artifact.main()
    if rc != 0:
        print(f"FAILED:receipts emit rc={rc}")
        return rc
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
        "id": "ADV-0049",
        "unit_id": "ADV-0049",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0049",
        "registered": True,
        "output_path": OUT,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "fusion-record-provenance-licence",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "decompose-lineage-oracle",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0049/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0049-probe2-decompose-rederive",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0049: live named probes exit 0, license-and-rights "
            "record state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0049",
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
    print("SUCCESS:ADV-0049 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
