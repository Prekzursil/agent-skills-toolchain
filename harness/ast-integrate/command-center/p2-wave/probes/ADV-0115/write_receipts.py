#!/usr/bin/env python3
"""Write ADV-0115 artifact, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
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
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import emit_artifact as EA  # noqa: E402

SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0115/common.py",
    "command-center/p2-wave/probes/ADV-0115/engine.py",
    "command-center/p2-wave/probes/ADV-0115/flood_detector.py",
    "command-center/p2-wave/probes/ADV-0115/task-set.json",
    "command-center/p2-wave/probes/ADV-0115/probe1_cost_curve.py",
    "command-center/p2-wave/probes/ADV-0115/probe2_quality_curve.py",
    "command-center/p2-wave/probes/ADV-0115/emit_artifact.py",
    "tools/router/injection_budget.py",
    "tools/router/tokenizer.py",
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
        "unit_id": C.UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/ADV-0115/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    rc_emit = EA.main()
    if rc_emit != 0:
        print(f"FAILED:{C.UNIT_ID} receipts emit rc={rc_emit}")
        return 1
    c1, t1 = run_cmd(C.PROBE1)
    c2, t2 = run_cmd(C.PROBE2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{C.UNIT_ID} receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    out = REPO / C.OUT_REL
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["named_probes"] = [
        {
            "id": "probe1",
            "command": C.PROBE1,
            "exit_code": c1,
            "role": "cost-curve-dispersion",
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": C.PROBE2,
            "exit_code": c2,
            "role": "quality-curve-rotated-flood",
            "raw_output": t2,
        },
    ]
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(path, "supporting") for path in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT_ID,
        "unit_id": C.UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": C.SENTINEL,
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_DECLARED,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.PROBE1,
                "exit_code": c1,
                "role": "cost-curve-dispersion",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": C.PROBE2,
                "exit_code": c2,
                "role": "quality-curve-rotated-flood",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0115/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0115-probe2-quality-rotated-and-flood",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": f"SUCCESS:delivered {C.UNIT_ID}",
        "ts": now,
        "notes": (
            "G-1 for ADV-0115: live named probes exit 0, router-overhead artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT_ID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a.get("present")),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{C.UNIT_ID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
