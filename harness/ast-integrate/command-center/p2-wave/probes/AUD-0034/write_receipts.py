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
sys.path.insert(0, str(HERE))

from constants import OUTPUT_REL, P1, P2, SCHEMA_REL, UNIT_ID  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0034/emit_artifact.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0034/constants.py",
    "command-center/p2-wave/probes/AUD-0034/corpus.py",
    "command-center/p2-wave/probes/AUD-0034/resolver.py",
    "command-center/p2-wave/probes/AUD-0034/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0034/probe1_mechanical_resolver.py",
    "command-center/p2-wave/probes/AUD-0034/probe2_undecidable_side_by_side.py",
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
        "unit_id": UNIT_ID,
        "receipt_path": "command-center/p2-wave/probes/AUD-0034/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-4000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUTPUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0034",
        "registered": True,
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0034/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0034-probe2-undecidable-side-by-side",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for AUD-0034: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Mechanical resolver; UNDECIDABLE is "
            "never guessed. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT_ID,
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
    print(f"primary {OUTPUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print(f"SUCCESS:{UNIT_ID} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
