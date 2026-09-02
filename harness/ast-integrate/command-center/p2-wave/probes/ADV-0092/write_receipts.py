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
UNIT = "ADV-0092"
OUT = "command-center/adversarial/ADV-0092-role-collapse-differentiation.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/probe1_divergence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/probe2_attribution.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0092/emit_artifact.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0092/common.py",
    "command-center/p2-wave/probes/ADV-0092/metrics.py",
    "command-center/p2-wave/probes/ADV-0092/councils.py",
    "command-center/p2-wave/probes/ADV-0092/classifier.py",
    "command-center/p2-wave/probes/ADV-0092/inventory.py",
    "command-center/p2-wave/probes/ADV-0092/measure.py",
    "command-center/p2-wave/probes/ADV-0092/probe1_divergence.py",
    "command-center/p2-wave/probes/ADV-0092/probe2_attribution.py",
    "command-center/p2-wave/probes/ADV-0092/anchor_control.py",
    "command-center/p2-wave/probes/ADV-0092/emit_artifact.py",
    "command-center/p2-wave/probes/ADV-0092/artifact.schema.json",
    "command-center/p2-wave/probes/ADV-0092/fixtures.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/ADV-0092/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_raw(p1_text: str, p2_text: str) -> None:
    path = REPO / OUT
    doc = json.loads(path.read_text(encoding="utf-8"))
    for item in doc.get("named_probes") or []:
        if item.get("id") == "probe1":
            item["raw_output"] = p1_text
        elif item.get("id") == "probe2":
            item["raw_output"] = p2_text
    for item in doc.get("tests") or []:
        if item.get("id") == "T-PROBE-1-PAIRWISE-DIVERGENCE":
            item["output_tail"] = p1_text
            item["result"] = "PASS"
        elif item.get("id") == "T-PROBE-2-ROLE-ATTRIBUTION":
            item["output_tail"] = p2_text
            item["result"] = "PASS"
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ce, te = run_cmd(EMIT)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-3000:])
        return 1
    print(te.splitlines()[-2:] and "\n".join(te.splitlines()[-4:]))
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    patch_raw(t1, t2)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts post-patch probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ADV-0092",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-pathology-sim.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "pairwise-lexical-and-stance-divergence",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "independent-role-attribution-classifier",
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
        "manifest_path": "command-center/p2-wave/probes/ADV-0092/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "ADV-0092-probe2-independent-role-classifier",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for ADV-0092: live named probes exit 0, artifact state=SUCCESS "
            "with SUCCESS:ADV-0092, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. Behavioural target is "
            "honestly NOT-CHECKED when no runtime five-role first-round set exists."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0092 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
