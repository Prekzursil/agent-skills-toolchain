#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/wfa/WFA-0058-mechanism-vocabulary.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0058/probe1_mapping_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0058/probe2_discrimination_reviewer.py"
)
SUPPORTING = [
    "command-center/wfa/mechanism-registry.json",
    "command-center/p2-wave/probes/WFA-0058/vocab.py",
    "command-center/p2-wave/probes/WFA-0058/mapper.py",
    "command-center/p2-wave/probes/WFA-0058/corpus.py",
    "command-center/p2-wave/probes/WFA-0058/discriminate.py",
    "command-center/p2-wave/probes/WFA-0058/namespaces.py",
    "command-center/p2-wave/probes/WFA-0058/reviewer.py",
    "command-center/p2-wave/probes/WFA-0058/mechanism-record.schema.json",
    "command-center/p2-wave/probes/WFA-0058/probe1_mapping_both_states.py",
    "command-center/p2-wave/probes/WFA-0058/probe2_discrimination_reviewer.py",
    "command-center/p2-wave/probes/WFA-0058/emit_artifact.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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
        "unit_id": "WFA-0058",
        "receipt_path": "command-center/p2-wave/probes/WFA-0058/SUBAGENT-RETURN.json",
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
        "id": "WFA-0058",
        "unit_id": "WFA-0058",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0058",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/wfa/schema/wfa-schema-pack.json#/$defs/MechanismRecord"
        ),
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
        "manifest_path": "command-center/p2-wave/probes/WFA-0058/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "WFA-0058-both-states-discrimination-rerun",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
        },
        "ts": now,
        "notes": (
            "G-1 for WFA-0058: closed MX-NNNN vocabulary, mapping table "
            "with NEW-MECHANISM gaps, 20-example blind discrimination, "
            "live named probes exit 0, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. Live candidate registry is "
            "absent; stand-in is catalog-derived, not a fake 282-row census."
        ),
        "measure_line": "",
        "cloud_ok": False,
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "WFA-0058",
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
    print("SUCCESS:WFA-0058 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
