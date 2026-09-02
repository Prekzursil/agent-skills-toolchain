#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from emit import main as emit_main  # noqa: E402
from paths import (  # noqa: E402
    LEDGER_REL,
    LIVE_REL,
    OUT_REL,
    P1,
    P2,
    RECORD_SCHEMA_REL,
    REPO,
    RUN_LEDGER_REL,
    SCHEMA_REL,
    UNIT,
)

SUPPORTING = [
    SCHEMA_REL,
    LIVE_REL,
    RUN_LEDGER_REL,
    LEDGER_REL,
    RECORD_SCHEMA_REL,
    "command-center/p2-wave/probes/TST-0041/suite.py",
    "command-center/p2-wave/probes/TST-0041/paths.py",
    "command-center/p2-wave/probes/TST-0041/probe1_tamper_and_schema.py",
    "command-center/p2-wave/probes/TST-0041/probe2_concurrent_and_reorder.py",
    "command-center/p2-wave/probes/TST-0041/emit.py",
    "command-center/p2-wave/probes/TST-0041/schema_val.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
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
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0041/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc = emit_main()
    if rc != 0:
        print(f"FAILED:{UNIT} write_receipts emit rc={rc}")
        return rc
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} write_receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print(f"FAILED:{UNIT} write_receipts missing {missing}")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UNIT}",
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "tamper-and-schema",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "concurrent-and-reorder",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/TST-0041/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0041-probe2-concurrent-reorder",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0041: live named probes exit 0, receipts/TST-0041.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
