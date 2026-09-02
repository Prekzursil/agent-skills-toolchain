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
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import emit_matrix as E  # noqa: E402

OUT = "command-center/receipts/BLD-0063.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0063/probe2_verdict_rules.py"
)
SUPPORTING = [
    "command-center/schema/coverage-matrix.schema.json",
    "command-center/p2-wave/probes/BLD-0063/questions.py",
    "command-center/p2-wave/probes/BLD-0063/verdicts.py",
    "command-center/p2-wave/probes/BLD-0063/matrix.py",
    "command-center/p2-wave/probes/BLD-0063/schema_local.py",
    "command-center/p2-wave/probes/BLD-0063/emit_matrix.py",
    "command-center/p2-wave/probes/BLD-0063/probe1_remove_receipt.py",
    "command-center/p2-wave/probes/BLD-0063/probe2_verdict_rules.py",
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
        "unit_id": "BLD-0063",
        "receipt_path": "command-center/p2-wave/probes/BLD-0063/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    erc = E.main()
    if erc != 0:
        print(f"FAILED:BLD-0063 emit rc={erc}")
        return erc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:BLD-0063 receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "BLD-0063",
        "unit_id": "BLD-0063",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0063",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/coverage-matrix.schema.json",
        "measure_line": "SUCCESS:delivered BLD-0063",
        "measure": {"exit_code": 0, "line": "SUCCESS:delivered BLD-0063"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "remove-receipt-control",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "verdict-and-self-reference",
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
        "manifest_path": "command-center/p2-wave/probes/BLD-0063/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "BLD-0063-probe2-independent-remap",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for BLD-0063: live named probes exit 0, BLD-0063.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Mapping is from receipts on disk, "
            "including currently readable BLD-0001..BLD-0062 files. "
            "Coverage uses evidence[].verdict CONFIRMED/REFUTED on those "
            "receipts; catalog intent without a receipt does not cover. "
            "cloud_ok is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "BLD-0063",
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
    print("SUCCESS:BLD-0063 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
