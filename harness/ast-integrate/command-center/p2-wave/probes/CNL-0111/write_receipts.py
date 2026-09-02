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
    "CNL-0111-normative-boards-ethics-legal-review-and-the-risk-committe.md"
)
SCHEMA = "command-center/schema/council-preset.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0111/probe1_instantiate_and_sibling.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0111/boards.py",
    "command-center/p2-wave/probes/CNL-0111/compose.py",
    "command-center/p2-wave/probes/CNL-0111/instantiate.py",
    "command-center/p2-wave/probes/CNL-0111/sibling.py",
    "command-center/p2-wave/probes/CNL-0111/schema_check.py",
    "command-center/p2-wave/probes/CNL-0111/council-preset.schema.json",
    "command-center/p2-wave/probes/CNL-0111/fixtures/task.json",
    "command-center/p2-wave/probes/CNL-0111/fixtures/both_permit.json",
    "command-center/p2-wave/probes/CNL-0111/probe1_instantiate_and_sibling.py",
    "command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py",
    "command-center/p2-wave/probes/CNL-0111/emit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
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
        "unit_id": "CNL-0111",
        "receipt_path": "command-center/p2-wave/probes/CNL-0111/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not (REPO / OUT).is_file():
        print("FAILED:CNL-0111 receipts primary missing")
        return 1
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
        "id": "CNL-0111",
        "unit_id": "CNL-0111",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0111",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "instantiate-and-nearest-sibling",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "schema-and-composition-negative-control",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0111/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0111-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0111: live named probes exit 0, preset family "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Legal PROHIBITED plus risk ACCEPT does "
            "not authorize. Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is "
            "absent; siblings are the CNL-0102 reconstruction."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0111",
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
    print("SUCCESS:CNL-0111 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
