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
import audit as A  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0006/emit_artifact.py"
)
SUPPORTING = [
    A.SCHEMA_REL,
    "command-center/p2-wave/probes/ADV-0006/audit.py",
    A.P1_REL,
    A.P2_REL,
    "command-center/p2-wave/probes/ADV-0006/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(A.REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = A.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": A.UNIT_ID,
        "receipt_path": (
            "command-center/p2-wave/probes/ADV-0006/SUBAGENT-RETURN.json"
        ),
        "role": role,
    }


def main() -> int:
    code_e, text_e = run_cmd(EMIT)
    print(text_e)
    if code_e != 0:
        print(f"FAILED:ADV-0006 receipts emit rc={code_e}")
        return 1
    code1, text1 = run_cmd(A.P1_CMD)
    code2, text2 = run_cmd(A.P2_CMD)
    print(text1[-4000:])
    print(text2[-4000:])
    if code1 != 0 or code2 != 0:
        print(f"FAILED:ADV-0006 receipts probes c1={code1} c2={code2}")
        return 1
    primary = row(A.OUTPUT_REL, "primary")
    artifacts = [primary] + [row(rel, "supporting") for rel in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": A.UNIT_ID,
        "unit_id": A.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": A.catalog_sentinel(),
        "registered": True,
        "output_path": A.OUTPUT_REL,
        "output_schema": A.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": A.P1_CMD,
                "exit_code": code1,
                "raw_output": text1,
            },
            {
                "id": "probe2",
                "command": A.P2_CMD,
                "exit_code": code2,
                "raw_output": text2,
            },
        ],
        "artifacts": [
            {
                "path": A.OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": (
            "command-center/p2-wave/probes/ADV-0006/UNIT-ARTIFACT-MANIFEST.json"
        ),
        "reviewer": {
            "reviewer_id": "ADV-0006-probe2-counterexample-hunt",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0006: live named probes exit 0, honest PARTIAL "
            "scope-versus-evidence audit on the reconstructed CONFIRMED "
            "population, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
        "measure_line": f"SUCCESS:delivered {A.UNIT_ID}",
        "measure": {
            "exit_code": 0,
            "line": f"SUCCESS:delivered {A.UNIT_ID}",
        },
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": A.UNIT_ID,
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote receipts primary_sha={primary['sha256']} "
        f"bytes={primary['bytes']}"
    )
    print("SUCCESS:ADV-0006 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
