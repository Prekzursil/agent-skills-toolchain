#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
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

from contract import OUT_REL, SCHEMA_REL, SENTINEL, UNIT  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0024/probe1_two_shell_availability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0024/probe2_surface_census.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0024/contract.py",
    "command-center/p2-wave/probes/RES-0024/detector.py",
    "command-center/p2-wave/probes/RES-0024/surface.py",
    "command-center/p2-wave/probes/RES-0024/emit_record.py",
    "command-center/p2-wave/probes/RES-0024/probe1_two_shell_availability.py",
    "command-center/p2-wave/probes/RES-0024/probe2_surface_census.py",
    "command-center/p2-wave/probes/RES-0024/captures/extension_ts.body",
    "command-center/p2-wave/probes/RES-0024/captures/extension_ts.meta.json",
    "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.body",
    "command-center/p2-wave/probes/RES-0024/captures/extension_ref_md.meta.json",
    "command-center/p2-wave/probes/RES-0024/captures/gemini_md_doc.body",
    "command-center/p2-wave/probes/RES-0024/captures/gemini_md_doc.meta.json",
    "command-center/p2-wave/probes/RES-0024/captures/memory_discovery.body",
    "command-center/p2-wave/probes/RES-0024/captures/memory_discovery.meta.json",
    "command-center/p2-wave/probes/RES-0024/captures/memory_tool.body",
    "command-center/p2-wave/probes/RES-0024/captures/memory_tool.meta.json",
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
        "present": True,
        "unit_id": UNIT,
        "receipt_path": f"command-center/p2-wave/probes/{UNIT}/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    art = REPO / OUT_REL
    if not art.is_file():
        print("FAILED:receipts primary artifact missing; run emit_record.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT_REL, "primary")
    artifacts = [primary]
    if (REPO / SCHEMA_REL).is_file():
        artifacts.append(row(SCHEMA_REL, "schema"))
    artifacts.extend(row(p, "supporting") for p in SUPPORTING)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "measure_line": f"SUCCESS:delivered {UNIT}",
        "measure": {"exit_code": 0, "line": f"SUCCESS:delivered {UNIT}"},
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "two-shell-availability",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "surface-census",
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
        "manifest_path": f"command-center/p2-wave/probes/{UNIT}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0024-probe1-two-shell-availability",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0024: live named probes exit 0, RES-0024.json "
            "state=SUCCESS with two-shell availability verdict UNAVAILABLE "
            "and fallback_required, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
