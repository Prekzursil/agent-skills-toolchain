#!/usr/bin/env python3
"""Write per-unit SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = (
    "command-center/design/council/"
    "CNL-0068-evidence-outranks-popularity-the-executable-test-override-.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py"
)
SUPPORTING = [
    "command-center/schema/council-design-note.schema.json",
    "command-center/p2-wave/probes/CNL-0068/override.py",
    "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py",
    "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py",
    "command-center/p2-wave/probes/CNL-0068/emit_note.py",
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
        "unit_id": "CNL-0068",
        "receipt_path": "command-center/p2-wave/probes/CNL-0068/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_note_test_results(c1: int, c2: int) -> None:
    path = REPO / OUT
    note = json.loads(path.read_text(encoding="utf-8"))
    results = {0: "PASS"}
    for item in note.get("tests") or []:
        if item.get("id") == "T1-unanimous-but-refuted":
            item["result"] = results.get(c1, "FAIL")
        if item.get("id") == "T2-converse-irrelevant-fail":
            item["result"] = results.get(c2, "FAIL")
    path.write_text(json.dumps(note, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    emit_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNL-0068/emit_note.py"
    )
    ce, te = run_probe(emit_cmd)
    if ce != 0:
        print(f"FAILED:receipts emit rc={ce}")
        print(te[-2000:])
        return 1
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1
    patch_note_test_results(c1, c2)
    # Re-run probe2 after the note's tests[].result field changes, so G-1
    # re-execution still matches a note that probe2 schema-validates.
    c2b, t2b = run_probe(P2)
    if c2b != 0:
        print(f"FAILED:receipts probe2-after-patch c2={c2b}")
        print(t2b[-1500:])
        return 1
    t2 = t2b
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0068",
        "unit_id": "CNL-0068",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0068",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-design-note.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unanimous-but-refuted",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "converse-and-independent-recount",
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0068/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0068-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0068: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0068",
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
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0068 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
