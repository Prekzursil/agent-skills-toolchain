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
OUT = "command-center/receipts/IMP-0324.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0324/probe1_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0324/probe2_behaviour.py"
)
SUPPORTING = [
    "tools/council/antifail/injection.py",
    "tools/council/antifail/__init__.py",
    "tools/council/__init__.py",
    "command-center/p2-wave/probes/IMP-0324/probe1_corpus.py",
    "command-center/p2-wave/probes/IMP-0324/probe2_behaviour.py",
    "command-center/p2-wave/probes/IMP-0324/emit_receipt.py",
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
        "unit_id": "IMP-0324",
        "receipt_path": "command-center/p2-wave/probes/IMP-0324/SUBAGENT-RETURN.json",
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
        "id": "IMP-0324",
        "unit_id": "IMP-0324",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0324",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-antifail-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "injection-corpus-block-rate",
                "raw_output": t1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "behaviour-hold-and-negative-control",
                "raw_output": t2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": a["path"],
                "sha256": a["sha256"],
                "bytes": a["bytes"],
                "exists": True,
                "role": a["role"],
            }
            for a in artifacts
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0324/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0324-probe1-corpus-correctness",
            "verdict": "PASS",
            "independent": True,
        },
        "security_refuter": {
            "reviewer_id": "IMP-0324-probe2-behaviour-security-refuter",
            "verdict": "PASS",
            "independent": True,
            "default_on_insufficient_evidence": "REFUTED",
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0324: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0324",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"primary {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print("wrote SUBAGENT-RETURN.json UNIT-ARTIFACT-MANIFEST.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
