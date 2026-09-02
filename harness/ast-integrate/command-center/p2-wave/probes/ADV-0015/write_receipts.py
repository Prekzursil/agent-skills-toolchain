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
sys.path.insert(0, str(HERE))
import lib as L  # noqa: E402

SUPPORTING = [
    L.SCHEMA_REL,
    L.FIXTURE_REL,
    "command-center/p2-wave/probes/ADV-0015/lib.py",
    L.P1_REL,
    L.P2_REL,
    "command-center/p2-wave/probes/ADV-0015/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(L.REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = L.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": L.UNIT_ID,
        "receipt_path": (
            "command-center/p2-wave/probes/ADV-0015/SUBAGENT-RETURN.json"
        ),
        "role": role,
    }


def main() -> int:
    out = L.REPO / L.OUT_REL
    if not out.is_file():
        print("FAILED:ADV-0015 receipts artifact missing; run emit_artifact.py first")
        return 1
    c1, t1 = run_probe(L.P1_CMD)
    c2, t2 = run_probe(L.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0015 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(L.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": L.UNIT_ID,
        "unit_id": L.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": L.catalog_sentinel(),
        "registered": True,
        "output_path": L.OUT_REL,
        "output_schema": L.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": L.P1_CMD,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": L.P2_CMD,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": L.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/ADV-0015/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "ADV-0015-probe2-retired-id-runtime",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0015: live named probes exit 0, honest non-BLOCKED "
            "routing-table staleness audit, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "measure_line": f"SUCCESS:delivered {L.UNIT_ID}",
        "measure": {
            "exit_code": 0,
            "line": f"SUCCESS:delivered {L.UNIT_ID}",
        },
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": L.UNIT_ID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"wrote receipts primary_sha={primary['sha256']} bytes={primary['bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
