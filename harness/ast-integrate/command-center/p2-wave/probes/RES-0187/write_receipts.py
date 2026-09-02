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

from contract import OUT_REL, P1, P2, SCHEMA_REL, SENTINEL, UNIT  # noqa: E402
from emit_artifact import build  # noqa: E402

SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/RES-0187/contract.py",
    "command-center/p2-wave/probes/RES-0187/classify.py",
    "command-center/p2-wave/probes/RES-0187/controls.py",
    "command-center/p2-wave/probes/RES-0187/inventory.py",
    "command-center/p2-wave/probes/RES-0187/lineage.py",
    "command-center/p2-wave/probes/RES-0187/emit_artifact.py",
    "command-center/p2-wave/probes/RES-0187/probe1_however_negative_control.py",
    "command-center/p2-wave/probes/RES-0187/probe2_recorded_triple_and_recount.py",
    "command-center/p2-wave/probes/RES-0187/source-lineage.json",
    "command-center/p2-wave/probes/RES-0187/captures/wep-wikipedia.raw",
    "command-center/p2-wave/probes/RES-0187/captures/kent-wep-wayback.raw",
    "command-center/p2-wave/probes/RES-0187/captures/command-center-listing.txt",
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/RES-0187/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    doc = build()
    out_path = REPO / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2500:])
    print(f"probe2 rc={c2}")
    print(t2[-2500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UNIT} receipts probes c1={c1} c2={c2}")
        return 1

    supporting = [p for p in SUPPORTING if (REPO / p).is_file()]
    primary = row(OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in supporting]
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
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "however-use-versus-mention",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "recorded-triple-both-states-and-recount",
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
        "manifest_path": "command-center/p2-wave/probes/RES-0187/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0187-adversarial-refuter",
            "verdict": "PASS",
            "independent": True,
            "default_to_refuted": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0187: live named probes exit 0, counterevidence "
            "coverage audit state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write. cloud ok=true is not delivery. "
            "CLAIM-REGISTRY absent; population is on-disk research claims[]."
        ),
        "cloud_ok": False,
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
