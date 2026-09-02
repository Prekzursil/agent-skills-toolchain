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
UNIT = "CNF-0068"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0068/probe1_both_outcomes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0068/probe2_independent.py"
)
SUPPORTING = [
    "command-center/schema/adjudication-report.schema.json",
    "command-center/p2-wave/probes/CNF-0068/adjudicate.py",
    "command-center/p2-wave/probes/CNF-0068/reviewer_a.py",
    "command-center/p2-wave/probes/CNF-0068/reviewer_b.py",
    "command-center/p2-wave/probes/CNF-0068/fixtures/claims.json",
    "command-center/p2-wave/probes/CNF-0068/emit_report.py",
    "command-center/p2-wave/probes/CNF-0068/schema_offline.py",
    "command-center/p2-wave/probes/CNF-0068/probe1_both_outcomes.py",
    "command-center/p2-wave/probes/CNF-0068/probe2_independent.py",
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
        check=False,
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
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/CNF-0068/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    catalog = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next(u for u in catalog["work_units"] if u.get("id") == UNIT)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    schema_rel = str(unit["output_schema"]).replace("\\", "/")
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(out_rel, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0068",
        "registered": True,
        "output_path": out_rel,
        "output_schema": schema_rel,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2},
        ],
        "artifacts": [
            {
                "path": out_rel,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNF-0068/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNF-0068-probe2-independent",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNF-0068: live named probes exit 0, contradiction "
            "adjudication state=SUCCESS, per-unit manifest row. Did not run "
            "global unit_manifest.py --write."
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
    print(f"primary {out_rel} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNF-0068 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
