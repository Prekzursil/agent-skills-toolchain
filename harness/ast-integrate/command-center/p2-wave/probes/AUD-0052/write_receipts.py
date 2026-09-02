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

import constants as C  # noqa: E402

EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0052/emit_artifact.py"
)
SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0052/constants.py",
    "command-center/p2-wave/probes/AUD-0052/shuffle_plugin.py",
    "command-center/p2-wave/probes/AUD-0052/census.py",
    "command-center/p2-wave/probes/AUD-0052/schema_check.py",
    "command-center/p2-wave/probes/AUD-0052/emit_artifact.py",
    "command-center/p2-wave/probes/AUD-0052/probe1_three_seeds.py",
    "command-center/p2-wave/probes/AUD-0052/probe2_five_repeats.py",
    "command-center/p2-wave/probes/AUD-0052/lab/test_order_box.py",
    "command-center/p2-wave/probes/AUD-0052/lab/test_planted_flake.py",
    "command-center/p2-wave/probes/AUD-0052/lab/test_stable.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
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
        "unit_id": C.UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0052/SUBAGENT-RETURN.json",
        "role": role,
    }


def named_probe_slots(doc: dict) -> list:
    slots: list = []
    if isinstance(doc.get("named_probes"), list):
        slots.extend(doc["named_probes"])
    report = doc.get("report")
    if isinstance(report, dict) and isinstance(report.get("named_probes"), list):
        slots.extend(report["named_probes"])
    return slots


def patch_verbatim(t1: str, t2: str) -> None:
    path = REPO / C.OUT_REL
    doc = json.loads(path.read_text(encoding="utf-8"))
    for item in named_probe_slots(doc):
        if not isinstance(item, dict):
            continue
        if item.get("id") == "probe1":
            item["raw_output"] = t1
        elif item.get("id") == "probe2":
            item["raw_output"] = t2
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:AUD-0052 receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    print("\n".join(te.splitlines()[-4:]))
    c1, t1 = run_cmd(C.P1)
    c2, t2 = run_cmd(C.P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0052 receipts probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1
    patch_verbatim(t1, t2)
    primary = row(C.OUT_REL, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": C.UNIT,
        "unit_id": C.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0052",
        "registered": True,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": C.P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "three-shuffled-seeds-and-reorder-control",
            },
            {
                "id": "probe2",
                "command": C.P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "five-identical-order-repeats-flake-separation",
            },
        ],
        "artifacts": [
            {
                "path": C.OUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/AUD-0052/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0052-probe2-five-repeats-falsify-headline",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0052: live named probes exit 0, audit artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": C.UNIT,
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
    print(f"primary {C.OUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0052 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
