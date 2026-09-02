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
    "CNL-0055-saturation-versus-quota-filling-at-the-100-idea-target.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0055/probe2_negative_control.py"
)
SUPPORTING = [
    "command-center/schema/council-design-note.schema.json",
    "command-center/p2-wave/probes/CNL-0055/detector.py",
    "command-center/p2-wave/probes/CNL-0055/fixtures.py",
    "command-center/p2-wave/probes/CNL-0055/probe1_both_states.py",
    "command-center/p2-wave/probes/CNL-0055/probe2_negative_control.py",
    "command-center/p2-wave/probes/CNL-0055/emit_note.py",
    "command-center/p2-wave/probes/CNL-0055/fixtures/padding.json",
    "command-center/p2-wave/probes/CNL-0055/fixtures/saturated.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
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
        "unit_id": "CNL-0055",
        "receipt_path": "command-center/p2-wave/probes/CNL-0055/SUBAGENT-RETURN.json",
        "role": role,
    }


def patch_test_results(c1: int, c2: int) -> None:
    art = REPO / OUT
    doc = json.loads(art.read_text(encoding="utf-8"))
    tests = doc.get("tests") or []
    for t in tests:
        if t.get("id") == "both-states-padding-vs-saturated":
            t["result"] = "PASS" if c1 == 0 else "FAIL"
        if t.get("id") == "negative-control-independent-recount":
            t["result"] = "PASS" if c2 == 0 else "FAIL"
    art.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    patch_test_results(c1, c2)
    c1b, t1b = run_probe(P1)
    c2b, t2b = run_probe(P2)
    if c1b != 0 or c2b != 0:
        print(f"FAILED:receipts post-patch probes c1={c1b} c2={c2b}")
        print(t1b[-2000:])
        print(t2b[-2000:])
        return 1
    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "CNL-0055",
        "unit_id": "CNL-0055",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0055",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/council-design-note.schema.json",
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-states-padding-vs-saturated",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "negative-control-independent-recount",
                "raw_output": t2b,
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
        "manifest_path": "command-center/p2-wave/probes/CNL-0055/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0055-probe2-independent-trigram-recount",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNL-0055: live named probes exit 0, design note "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. CNL-0051/CNL-0078 remain absent; "
            "local Jaccard unique counter is a scoped stand-in."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0055",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:CNL-0055 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
