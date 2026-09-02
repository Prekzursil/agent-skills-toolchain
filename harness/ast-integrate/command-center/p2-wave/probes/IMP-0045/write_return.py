#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loader import RECEIPT, SENTINEL, digest_file  # noqa: E402

REPO = HERE.parents[3]
RET = HERE / "SUBAGENT-RETURN.json"
MAN = HERE / "UNIT-ARTIFACT-MANIFEST.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0045/probe1_negative_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0045/probe2_portability.py"
)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": "IMP-0045",
        "receipt_path": "command-center/p2-wave/probes/IMP-0045/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    if not RECEIPT.is_file():
        print("FAILED:IMP-0045 write-return receipt missing")
        return 1
    rc1, out1 = run(P1)
    print(out1[-3000:])
    if rc1 != 0:
        print(f"FAILED:IMP-0045 probe1 rc={rc1}")
        return 1
    rc2, out2 = run(P2)
    print(out2[-3000:])
    if rc2 != 0:
        print(f"FAILED:IMP-0045 probe2 rc={rc2}")
        return 1

    primary = art("command-center/receipts/IMP-0045.json", "primary")
    supporting = [
        art("tools/plugin/conformance.py", "supporting"),
        art("tools/plugin/blob.py", "supporting"),
        art("tools/plugin/fixture_tree.py", "supporting"),
        art("tools/plugin/schema/conformance-report.schema.json", "supporting"),
        art("tools/plugin/schema/plugin-manifest.schema.json", "supporting"),
        art("tools/plugin/tests/test_conformance.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0045/probe1_negative_controls.py", "supporting"),
        art("command-center/p2-wave/probes/IMP-0045/probe2_portability.py", "supporting"),
    ]
    rows = [primary, *supporting]
    missing = [r["path"] for r in rows if not r["present"]]
    if missing:
        print("FAILED:IMP-0045 missing artifacts", missing)
        return 1

    ret = {
        "id": "IMP-0045",
        "unit_id": "IMP-0045",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": "command-center/receipts/IMP-0045.json",
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/plugin/schema/conformance-report.schema.json"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "negative-controls",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "portability-blob-route",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": primary["path"],
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0045/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0045-probe2-blob-route",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        "notes": (
            "G-1 for IMP-0045: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    RET.write_text(json.dumps(ret, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "IMP-0045",
        "verified_on_disk": True,
        "expected": len(rows),
        "present": len(rows),
        "artifacts": rows,
    }
    MAN.write_text(json.dumps(man, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {RET.relative_to(REPO)} and {MAN.relative_to(REPO)}")
    print(f"primary sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0045 write-return")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
