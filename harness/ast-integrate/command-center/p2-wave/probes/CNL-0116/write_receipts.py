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
OUT = "command-center/design/council/CNL-0116-general-purpose-auto-composed-council-preset-the-flagship.md"
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0116/emit_artifact.py"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0116/probe1_instantiate.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0116/probe2_sibling_schema.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/CNL-0116/council-preset.schema.json",
    "command-center/p2-wave/probes/CNL-0116/composer.py",
    "command-center/p2-wave/probes/CNL-0116/probe1_instantiate.py",
    "command-center/p2-wave/probes/CNL-0116/probe2_sibling_schema.py",
    "command-center/p2-wave/probes/CNL-0116/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/p2-wave/probes/CNL-0116/fixtures/tasks.json",
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
        env={**dict(**{k: v for k, v in __import__("os").environ.items()}), "PYTHONDONTWRITEBYTECODE": "1"},
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
        "unit_id": "CNL-0116",
        "receipt_path": "command-center/p2-wave/probes/CNL-0116/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_probe(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit c={ce}")
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
        "id": "CNL-0116",
        "unit_id": "CNL-0116",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0116",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/p2-wave/probes/CNL-0116/council-preset.schema.json",
        "catalog_output_schema": "command-center/schema/council-preset.schema.json",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0116/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0116-probe2-sibling-schema",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0116: live named probes exit 0, flagship preset "
            "state=SUCCESS, per-unit UNIT-ARTIFACT-MANIFEST.json. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery. "
            "12-COUNCIL library bytes absent; nearest sibling is fixture C-M01. "
            "Catalog output_schema path is occupied by CNL-0107 "
            "($defs.council_preset); this unit's executable contract is "
            "probes/CNL-0116/council-preset.schema.json ($defs.preset_record)."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0116",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    payload_ret = json.dumps(ret, indent=1, sort_keys=True) + "\n"
    payload_man = json.dumps(man, indent=1, sort_keys=True) + "\n"
    for name in ("SUBAGENT-RETURN.json", "SUBAGENT-RETURN.json"):
        (HERE / name).write_text(payload_ret, encoding="utf-8")
    for name in ("UNIT-ARTIFACT-MANIFEST.json", "UNIT-ARTIFACT-MANIFEST.json"):
        (HERE / name).write_text(payload_man, encoding="utf-8")
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0116 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
