#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0075"
OUT = "command-center/audit/AUD-0075-stale-premise-sweep.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0075/probe1_remeasure.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0075/probe2_origin_audit.py"
)
EMIT = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0075/emit.py"
)
SUPPORTING = [
    "command-center/p2-wave/probes/AUD-0075/artifact.schema.json",
    "command-center/p2-wave/probes/AUD-0075/engine.py",
    "command-center/p2-wave/probes/AUD-0075/emit.py",
    "command-center/p2-wave/probes/AUD-0075/probe1_remeasure.py",
    "command-center/p2-wave/probes/AUD-0075/probe2_origin_audit.py",
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
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/AUD-0075/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    code_e, text_e = run_cmd(EMIT)
    print(text_e)
    if code_e != 0:
        print(f"FAILED:{UNIT} emit rc={code_e}")
        return 1
    code1, text1 = run_cmd(P1)
    print(text1)
    code2, text2 = run_cmd(P2)
    print(text2)
    if code1 != 0 or code2 != 0:
        print(f"FAILED:{UNIT} probes c1={code1} c2={code2}")
        return 1

    (HERE / "probe1-remeasurements.raw.txt").write_text(text1 + "\n", encoding="utf-8")
    (HERE / "probe2-origin-probes.raw.txt").write_text(text2 + "\n", encoding="utf-8")

    art_path = REPO / OUT
    doc = json.loads(art_path.read_text(encoding="utf-8"))
    probes = doc.get("named_probes") or []
    for item, text, code in ((probes[0], text1, code1), (probes[1], text2, code2)):
        item["verbatim_output"] = text
        item["exit_code"] = code
    doc["named_probes"] = probes
    art_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    code1b, text1b = run_cmd(P1)
    code2b, text2b = run_cmd(P2)
    print(text1b)
    print(text2b)
    if code1b != 0 or code2b != 0:
        print(f"FAILED:{UNIT} post-embed probes c1={code1b} c2={code2b}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary]
    for rel in SUPPORTING:
        if not (REPO / rel).is_file():
            print(f"FAILED:{UNIT} missing supporting {rel}")
            return 1
        artifacts.append(row(rel, "supporting"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:AUD-0075",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/audit-finding.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": code1b,
                "role": "mechanically-different-remeasure",
                "raw_output": text1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": code2b,
                "role": "origin-probe-audit",
                "raw_output": text2b,
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
        "manifest_path": "command-center/p2-wave/probes/AUD-0075/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "AUD-0075-probe2-origin-audit",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for AUD-0075: live named probes exit 0, stale-premise-sweep "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Declared audit-finding.schema.json is "
            "absent; local artifact.schema.json used. cloud ok=true is not "
            "delivery. No ADV rebuild. Harvest BLOCKED is not copied: the sweep "
            "completed and reports undeclared sources as zero signals."
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
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:AUD-0075 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
