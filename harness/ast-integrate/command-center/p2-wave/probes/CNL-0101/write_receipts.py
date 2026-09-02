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
OUT = (
    "command-center/design/council/"
    "CNL-0101-a-preset-is-a-typed-delta-over-councilspec-not-a-fork.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0101/probe1_schema_and_keys.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py"
)
SUPPORTING = [
    "command-center/schema/council-preset.schema.json",
    "command-center/p2-wave/probes/CNL-0101/corpus.py",
    "command-center/p2-wave/probes/CNL-0101/emit_artifact.py",
    "command-center/p2-wave/probes/CNL-0101/probe1_schema_and_keys.py",
    "command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py",
    "command-center/p2-wave/probes/CNL-0101/fixtures/preset.record.schema.json",
    "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
    "command-center/p2-wave/probes/CNL-0101/fixtures/base_spec_v1.json",
    "command-center/p2-wave/probes/CNL-0101/fixtures/base_spec_v2.json",
    "command-center/p2-wave/probes/CNL-0101/fixtures/invalid_preset.json",
    "command-center/p2-wave/probes/CNL-0101/fixtures/silent_non_editable.json",
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
        "unit_id": "CNL-0101",
        "receipt_path": "command-center/p2-wave/probes/CNL-0101/SUBAGENT-RETURN.json",
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
        "id": "CNL-0101",
        "unit_id": "CNL-0101",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0101",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-preset.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "schema-and-independent-key-recount",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "version-bump-and-non-editable-dial",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0101/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0101-probe1-schema-and-keys",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0101: live named probes exit 0, dossier state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; 72-record corpus is "
            "reconstructed catalog-class, not a library byte copy."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0101",
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
    print("SUCCESS:CNL-0101 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
