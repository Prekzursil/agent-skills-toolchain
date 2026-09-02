#!/usr/bin/env python3
"""Write ADV-0130 artifact, then per-unit SUBAGENT-RETURN and UNIT-ARTIFACT-MANIFEST."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import emit as E  # noqa: E402

OUT = "command-center/adversarial/ADV-0130-novelty-accounting.json"
SCHEMA = "command-center/schema/novelty-ledger.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0130/probe1_planted_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0130/probe2_independent_comm.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/ADV-0130/normalize.py",
    "command-center/p2-wave/probes/ADV-0130/engine.py",
    "command-center/p2-wave/probes/ADV-0130/comm_subtract.py",
    "command-center/p2-wave/probes/ADV-0130/emit.py",
    "command-center/p2-wave/probes/ADV-0130/schema_local.py",
    "command-center/p2-wave/probes/ADV-0130/probe1_planted_controls.py",
    "command-center/p2-wave/probes/ADV-0130/probe2_independent_comm.py",
    "command-center/p2-wave/probes/ADV-0130/fixtures/planted_filed.json",
    "command-center/UNKNOWNS-REGISTER.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{**subprocess.os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
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
        "unit_id": "ADV-0130",
        "receipt_path": "command-center/p2-wave/probes/ADV-0130/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    E.write()
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "ADV-0130",
        "unit_id": "ADV-0130",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0130",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "planted-controls",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-comm-subtract",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0130/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0130-posix-comm",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "measure_line": "SUCCESS:delivered ADV-0130",
        "ts": now,
        "notes": (
            "G-1 for ADV-0130: live named probes exit 0, novelty ledger "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "ADV-0130",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0130 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
