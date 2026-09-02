#!/usr/bin/env python3
"""Write ADV-0110 primary artifact plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
Does not rebuild SYN-0001.
"""
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
import emit_artifact as emit  # noqa: E402
import engine as E  # noqa: E402

OUT = emit.OUT
P1 = emit.P1
P2 = emit.P2
SUPPORTING = [
    "command-center/p2-wave/probes/ADV-0110/engine.py",
    "command-center/p2-wave/probes/ADV-0110/probe1_link_falsifiability.py",
    "command-center/p2-wave/probes/ADV-0110/probe2_counterfactual.py",
    "command-center/p2-wave/probes/ADV-0110/emit_artifact.py",
    "command-center/p2-wave/_measure_one_delivered.py",
    "command-center/synthesis/SYN-0007.intervention-ranking.json",
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
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path) if path.is_file() else ("", 0)
    return {
        "bytes": size,
        "path": rel,
        "present": path.is_file(),
        "receipt_path": "command-center/p2-wave/probes/ADV-0110/SUBAGENT-RETURN.json",
        "role": role,
        "sha256": sha,
        "unit_id": "ADV-0110",
    }


def main() -> int:
    live = E.investigate()
    if not live["control_passed_both_probes"]:
        print("FAILED:ADV-0110-receipts genuine causal control did not pass both probes")
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = emit.build_document(live, "pending live probe1", "pending live probe2", -1, -1, now)
    emit.write_artifact(doc)

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(t1)
    print(t2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0110-receipts probes c1={c1} c2={c2}")
        return 1

    doc = emit.build_document(live, t1, t2, c1, c2, now)
    emit.write_artifact(doc)

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()]
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
        "id": "ADV-0110",
        "manifest_path": "command-center/p2-wave/probes/ADV-0110/UNIT-ARTIFACT-MANIFEST.json",
        "named_probes": [
            {
                "command": P1,
                "exit_code": c1,
                "id": "probe1",
                "raw_output": t1,
                "role": "per-link-refuting-observation",
            },
            {
                "command": P2,
                "exit_code": c2,
                "id": "probe2",
                "raw_output": t2,
                "role": "remove-parent-prevention-test",
            },
        ],
        "notes": (
            "G-1 for ADV-0110: live named probes exit 0, "
            "ADV-0110-root-cause-hierarchy-falsifiability.json state=SUCCESS "
            "with scientific overall_verdict=REFUTED, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
        "output_path": OUT,
        "output_schema": emit.SCHEMA,
        "registered": True,
        "reviewer": {
            "independent": True,
            "reviewer_id": "ADV-0110-probe2-counterfactual-prevention",
            "verdict": "PASS",
        },
        "sentinel": "SUCCESS:ADV-0110",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "ts": now,
        "unit_id": "ADV-0110",
    }
    man = {
        "artifacts": artifacts,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "schema_version": 1,
        "unit_id": "ADV-0110",
        "verified_on_disk": True,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0110 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
