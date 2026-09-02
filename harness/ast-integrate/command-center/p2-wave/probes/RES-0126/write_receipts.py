#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json for RES-0126."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/research/RES-0126.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0126/probe1_capability_basis.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0126/probe2_not_flagged_control.py"
)
SUPPORTING = [
    ("command-center/p2-wave/probes/RES-0126/probe1_capability_basis.py", "named-probe"),
    ("command-center/p2-wave/probes/RES-0126/probe2_not_flagged_control.py", "named-probe"),
    ("command-center/p2-wave/probes/RES-0126/emit_record.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0126/inventory.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0126/sources.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0126/lib.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0126/write_receipts.py", "supporting"),
    ("command-center/p2-wave/probes/RES-0126/captures/FR-2020-10-05-2020-18334.html", "official-source"),
    ("command-center/p2-wave/probes/RES-0126/captures/FR-2021-10-21-2021-22774.html", "official-source"),
    ("command-center/p2-wave/probes/RES-0126/captures/FR-2022-05-26-2022-11282.html", "official-source"),
]
GRIND = HERE / ".grind-last.json"


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env)
    return p.returncode, ((p.stdout or "") + "\n" + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "bytes": size,
        "path": rel,
        "present": True,
        "receipt_path": "command-center/p2-wave/probes/RES-0126/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "RES-0126",
    }


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def park_blocked(required_fix: str, fp: str, errs: list[str]) -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "cloud_ok": False,
        "id": "RES-0126",
        "notes": (
            "Parked after two same-fingerprint structural refutes. No ADV rebuild circle."
        ),
        "output_path": OUT,
        "required_fix": required_fix,
        "state": "BLOCKED",
        "status": "BLOCKED",
        "structural_fingerprint": fp,
        "ts": now,
        "unit_id": "RES-0126",
        "why": errs,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:RES-0126 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def main() -> int:
    art = REPO / OUT
    if not art.is_file():
        print("FAILED:receipts primary artifact missing; run emit_record.py first")
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        err = f"c1={c1}\n{t1[-1500:]}\nc2={c2}\n{t2[-1500:]}"
        fp = fingerprint(err)
        last = {}
        if GRIND.is_file():
            try:
                last = json.loads(GRIND.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                last = {}
        GRIND.write_text(json.dumps({"fingerprint": fp, "err": err}, indent=2) + "\n", encoding="utf-8")
        if last.get("fingerprint") == fp:
            return park_blocked(
                required_fix="break-same-fingerprint:align-live-inventory-and-quoted-FR-spans",
                fp=fp,
                errs=[err],
            )
        print(f"FAILED:receipts probes c1={c1} c2={c2} fp={fp}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if GRIND.is_file():
        GRIND.unlink()
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, role) for p, role in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = json.loads(art.read_text(encoding="utf-8"))
    ret = {
        "artifacts": [
            {
                "bytes": primary["bytes"],
                "exists": True,
                "path": OUT,
                "role": "primary",
                "sha256": primary["sha256"],
            }
        ],
        "cloud_ok": False,
        "id": "RES-0126",
        "manifest_path": "command-center/p2-wave/probes/RES-0126/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {"command": P1, "exit_code": c1, "id": "probe1", "raw_output": t1},
            {"command": P2, "exit_code": c2, "id": "probe2", "raw_output": t2},
        ],
        "notes": (
            "G-1 for RES-0126: live named probes exit 0, research/RES-0126.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud_ok=false. Record is a "
            "factual landscape, not a legal conclusion."
        ),
        "output_path": OUT,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "registered": True,
        "required_fix": None,
        "reviewer": {
            "independent": True,
            "reviewer_id": "RES-0126-probe2-not-flagged-control",
            "verdict": "PASS",
        },
        "sentinel": doc.get("sentinel") or doc.get("completion_sentinel"),
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "RES-0126",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": len(artifacts),
        "schema_version": 1,
        "unit_id": "RES-0126",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0126 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
