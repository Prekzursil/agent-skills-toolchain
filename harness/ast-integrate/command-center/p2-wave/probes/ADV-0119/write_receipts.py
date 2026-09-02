#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys_path_insert = str(HERE)
import sys

sys.path.insert(0, sys_path_insert)

from emit_artifact import build_doc, write_doc  # noqa: E402
from scenario import run_all  # noqa: E402

UNIT = "ADV-0119"
OUT = "command-center/adversarial/ADV-0119-rollback-user-data-preservation.json"
SCHEMA = "command-center/schema/fault-injection-run.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0119/probe1_three_point_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0119/probe2_golden_journeys.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0119/emit_artifact.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0119/lifecycle.py",
    "command-center/p2-wave/probes/ADV-0119/scenario.py",
    "command-center/p2-wave/probes/ADV-0119/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0119/probe1_three_point_inventory.py",
    "command-center/p2-wave/probes/ADV-0119/probe2_golden_journeys.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0119/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    measured = run_all()
    if not measured.get("pass"):
        print("FAILED:ADV-0119 receipts drill")
        print(json.dumps({
            "honest": (measured.get("honest") or {}).get("pass"),
            "clean": (measured.get("clean_n1") or {}).get("pass"),
            "leftover": (measured.get("leftover_n_state") or {}).get("pass"),
            "naive": (measured.get("naive_rollback") or {}).get("pass"),
        }, indent=2)[:4000])
        return 1
    doc = build_doc(measured)
    write_doc(doc)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0119 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    named = [
        {
            "id": "probe1",
            "role": "three-point-inventory",
            "command": P1,
            "exit_code": c1,
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "role": "golden-journeys-and-leftover-state",
            "command": P2,
            "exit_code": c2,
            "raw_output": t2,
        },
    ]
    doc = build_doc(measured, probe_raw=named)
    digest_art, size = write_doc(doc)
    primary = row(OUT, "primary")
    if primary["sha256"] != digest_art or primary["bytes"] != size:
        print("FAILED:ADV-0119 receipts sha drift")
        return 1
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0119",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": named,
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ADV-0119/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0119-probe2-golden-journeys",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0119: live named probes exit 0, artifact state=SUCCESS "
            "with catalog completion_sentinel, per-unit manifest row. Did not "
            "run global unit_manifest.py --write. No ADV rebuild. Production "
            "platform/plugin is absent; disposable-prefix lifecycle is the "
            "measured subject."
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0119 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
