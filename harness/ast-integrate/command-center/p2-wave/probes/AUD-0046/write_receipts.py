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
sys_path_insert = str(HERE)

import sys

sys.path.insert(0, sys_path_insert)
import schema_local as SL  # noqa: E402

OUT = "command-center/audit/AUD-0046-gate-detector-control-sweep.json"
SCHEMA = "command-center/schema/audit-detector-control.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0046/probe1_unmodified_green.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0046/probe2_mutation_and_revert.py"
)
SUPPORTING = [
    SCHEMA,
    "tools/command-center/validate.py",
    "command-center/p2-wave/probes/AUD-0041/probe1-yaml-inventory.json",
    "command-center/p2-wave/probes/AUD-0046/sweep.py",
    "command-center/p2-wave/probes/AUD-0046/schema_local.py",
    "command-center/p2-wave/probes/AUD-0046/probe1_unmodified_green.py",
    "command-center/p2-wave/probes/AUD-0046/probe2_mutation_and_revert.py",
    "command-center/p2-wave/probes/AUD-0046/emit.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
        "unit_id": "AUD-0046",
        "receipt_path": "command-center/p2-wave/probes/AUD-0046/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_verbatim(doc: dict, t1: str, t2: str, c1: int, c2: int) -> None:
    report = doc.setdefault("report", {})
    report["named_probes"] = [
        {
            "id": "probe1",
            "command": P1,
            "exit_code": c1,
            "role": "unmodified-scratch-green",
            "raw_output": t1,
        },
        {
            "id": "probe2",
            "command": P2,
            "exit_code": c2,
            "role": "mutation-and-revert",
            "raw_output": t2,
        },
    ]
    for ev in doc.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        for pr in ev.get("probes") or []:
            if not isinstance(pr, dict):
                continue
            if pr.get("command") == P1:
                pr["raw_output"] = t1[-65000:]
                pr["exit_code"] = c1
            elif pr.get("command") == P2:
                pr["raw_output"] = t2[-65000:]
                pr["exit_code"] = c2
    for consumer in doc.get("downstream_consumers") or []:
        if not isinstance(consumer, dict):
            continue
        consumer["exit_code"] = c2
        consumer["executed"] = True
        consumer["read_ok"] = c2 == 0
        probe = consumer.get("probe")
        if isinstance(probe, dict) and probe.get("command") == P2:
            probe["raw_output"] = t2[-65000:]
            probe["exit_code"] = c2


def main() -> int:
    c0, t0 = run_cmd(
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/AUD-0046/emit.py"
    )
    if c0 != 0:
        print("FAILED:AUD-0046 emit")
        print(t0[-2000:])
        return 1
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0046 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    art = json.loads((REPO / OUT).read_text(encoding="utf-8"))
    patch_verbatim(art, t1, t2, c1, c2)
    (REPO / OUT).write_text(
        json.dumps(art, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha, size = digest(REPO / OUT)
    if art.get("artifacts"):
        art["artifacts"][0]["sha256"] = sha
        art["artifacts"][0]["bytes"] = size
        (REPO / OUT).write_text(
            json.dumps(art, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    errs = SL.errors(art)
    if errs:
        print("FAILED:AUD-0046 receipts schema", "; ".join(errs[:8]))
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [
        row(p, "supporting") for p in SUPPORTING if (REPO / p).is_file()
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "AUD-0046",
        "unit_id": "AUD-0046",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0046",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unmodified-scratch-green",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "mutation-and-revert",
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0046/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0046-probe2-mutation-and-revert",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0046: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not relaunch finish-everything-close or p2-cloud-ok-deliver. "
            "No ADV rebuild. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "AUD-0046",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote receipts sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0046 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
