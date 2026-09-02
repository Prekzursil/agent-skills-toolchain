#!/usr/bin/env python3
"""Emit ADV-0005 refutation record, SUBAGENT-RETURN, and per-unit manifest."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402

SUPPORTING = E.support_paths()
RETURN_REL = "command-center/p2-wave/probes/ADV-0005/SUBAGENT-RETURN.json"
MANIFEST_REL = "command-center/p2-wave/probes/ADV-0005/UNIT-ARTIFACT-MANIFEST.json"


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(E.REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    sha, size = E.digest_file(E.REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": E.UNIT,
        "receipt_path": RETURN_REL,
        "role": role,
    }


def main() -> int:
    c1, t1 = run_cmd(E.P1_CMD)
    c2, t2 = run_cmd(E.P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:ADV-0005-emit probes c1={c1} c2={c2}")
        print(t1[-3000:])
        print(t2[-3000:])
        return 1

    record = E.build_record(c1, t1, c2, t2)
    if str(record.get("state") or "").upper() in E.NOT_DELIVERING:
        print(f"FAILED:ADV-0005-emit state={record.get('state')}")
        return 1
    ok, why = E.validate_schema(record)
    if not ok:
        print(f"FAILED:ADV-0005-emit schema {why}")
        return 1
    text = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True)
    if E.CATALOG_SENTINEL not in text:
        print("FAILED:ADV-0005-emit sentinel-absent")
        return 1

    out = E.REPO / E.OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8", newline="\n")

    # Re-run probes now that the artifact exists so measure sees the same commands.
    c1b, t1b = run_cmd(E.P1_CMD)
    c2b, t2b = run_cmd(E.P2_CMD)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:ADV-0005-emit post-write probes c1={c1b} c2={c2b}")
        print(t1b[-3000:])
        print(t2b[-3000:])
        return 1

    record = E.build_record(c1b, t1b, c2b, t2b)
    ok, why = E.validate_schema(record)
    if not ok:
        print(f"FAILED:ADV-0005-emit rewrite schema {why}")
        return 1
    if str(record.get("state") or "").upper() in E.NOT_DELIVERING:
        print(f"FAILED:ADV-0005-emit rewrite state={record.get('state')}")
        return 1
    text = json.dumps(record, indent=2, sort_keys=True, ensure_ascii=True)
    out.write_text(text + "\n", encoding="utf-8", newline="\n")

    primary = row(E.OUTPUT_REL, "primary")
    man_rows = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": E.UNIT,
        "unit_id": E.UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": E.CATALOG_SENTINEL,
        "registered": True,
        "cloud_ok": False,
        "output_path": E.OUTPUT_REL,
        "output_schema": E.SCHEMA_REL,
        "named_probes": [
            {
                "id": "probe1",
                "command": E.P1_CMD,
                "exit_code": c1b,
                "raw_output": t1b,
                "role": "blind-rederive-source-and-question-only",
            },
            {
                "id": "probe2",
                "command": E.P2_CMD,
                "exit_code": c2b,
                "raw_output": t2b,
                "role": "unblind-diff-and-named-settling-tiebreak",
            },
        ],
        "artifacts": [
            {
                "path": E.OUTPUT_REL,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": MANIFEST_REL,
        "reviewer": {
            "reviewer_id": "ADV-0005-probe2-unblind-tiebreak",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for ADV-0005: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "No ADV rebuild of CLAIM-REGISTRY.json. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": E.UNIT,
        "verified_on_disk": True,
        "expected": len(man_rows),
        "present": len(man_rows),
        "artifacts": man_rows,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {E.OUTPUT_REL} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:ADV-0005-emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
