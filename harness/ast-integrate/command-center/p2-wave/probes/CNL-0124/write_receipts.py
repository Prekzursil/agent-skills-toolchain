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
OUT = (
    "command-center/design/council/"
    "CNL-0124-council-as-a-first-class-workflow-type-on-the-single-contr.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0124/council-design-note.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0124/probe1_inventory.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py"
)
SUPPORTING = [
    SCHEMA,
    LOCAL_SCHEMA,
    "command-center/p2-wave/probes/CNL-0124/plane.py",
    "command-center/p2-wave/probes/CNL-0124/capabilities.py",
    "command-center/p2-wave/probes/CNL-0124/compile.py",
    "command-center/p2-wave/probes/CNL-0124/probe1_inventory.py",
    "command-center/p2-wave/probes/CNL-0124/probe2_duplicate_plane.py",
    "command-center/p2-wave/probes/CNL-0124/emit_note.py",
    "command-center/p2-wave/probes/CNL-0124/fixtures/mapped-council.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/own-scheduler.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/langgraph-import.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/standing-watch.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/standing-own-loop.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/anonymous.json",
    "command-center/p2-wave/probes/CNL-0124/fixtures/nested.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**dict(__import__("os").environ))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "unit_id": "CNL-0124",
        "receipt_path": "command-center/p2-wave/probes/CNL-0124/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0124",
        "unit_id": "CNL-0124",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0124",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "inventory-mechanical",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "duplicate-control-plane",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0124/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0124-probe2-duplicate-plane",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "counterexample": "cx-own-turn-engine",
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0124: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Harness "
            "_USER-PROMPTS.md:10727/:10483 absent; cited via catalog."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0124",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0124 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
