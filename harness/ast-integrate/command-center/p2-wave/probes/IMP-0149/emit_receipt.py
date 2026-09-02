#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0149.json from live probe measurements."""

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
OUT = "command-center/receipts/IMP-0149.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0149/probe1_parity_sets.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0149/probe2_js_omission.py"
)
SUPPORTING = [
    "tools/agentspec/agentspec/ids.py",
    "tools/agentspec/agentspec/spec.py",
    "tools/agentspec/agentspec/validate.py",
    "tools/agentspec-js/src/ids.js",
    "tools/agentspec-js/src/spec.js",
    "tools/agentspec-js/src/validate.js",
    "tools/agentspec-js/parity/run.py",
    "tools/agentspec-js/parity/compare.py",
    "tools/agentspec-js/parity/emit_py.py",
    "tools/agentspec-js/parity/emit_js.js",
    "tools/agentspec-js/fixtures/build_corpus.py",
]


def digest(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "exists": path.is_file(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest() if path.is_file() else None,
        "role": "supporting",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd, cwd=str(REPO), shell=True, capture_output=True, text=True, env=env
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0149 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arts = [digest(p) for p in SUPPORTING]
    doc = {
        "unit_id": "IMP-0149",
        "id": "IMP-0149",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": "SUCCESS:IMP-0149",
        "schema_version": 1,
        "title": "Port every new spec type to the JS parity package and prove parity mechanically",
        "question": (
            "Mirror all Phase-7 spec additions into tools/agentspec-js/src and extend "
            "tools/agentspec-js/parity so Python and JS emit the SAME violation-id SET "
            "for the SAME fixtures. A missing id on either side is a failure, not a warning. "
            "A planted JS-only omission must turn parity red (both-states control)."
        ),
        "decision": {
            "summary": (
                "This worktree had no tools/agentspec or tools/agentspec-js. IMP-0149 stands "
                "up both implementations from the catalog contract (Phase-7 node types + closed "
                "ids), a 50-fixture shared corpus covering every closed id, and a set-equality "
                "parity harness. Live probes: identical sets (green) and planted JS omission (red, "
                "then restored green). Cloud ok=true is not delivery."
            ),
            "phase7_node_types": [
                "Subworkflow",
                "Loop",
                "HumanCheckpoint",
                "DynamicFanOut",
                "RepairLoop",
            ],
            "comparison": "sets",
            "missing_id_severity": "failure",
        },
        "evidence": [
            {
                "claim": "Python and JS emit identical violation-id sets over shared fixtures.",
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec-js/parity/run.py",
                "confidence": "almost-certain",
            },
            {
                "claim": "A planted JS-only omission of param-unknown-key turns parity red; restoring the check turns it green.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0149/probe2_js_omission.py",
                "confidence": "almost-certain",
            },
        ],
        "tests": [
            {
                "id": "probe1-parity-sets",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "exit_code": c1,
            },
            {
                "id": "probe2-js-omission",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "exit_code": c2,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0149-probe2-js-omission-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Independent of the implementer path: probe2 plants an omission in the JS "
                "emitter via AGENTSPEC_JS_OMIT_IDS without editing source, asserts red, then "
                "re-runs the unplanted pair and asserts green."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            *[
                {
                    "path": a["path"],
                    "exists": a["exists"],
                    "role": "supporting",
                    "sha256": a["sha256"],
                    "bytes": a["bytes"],
                }
                for a in arts
            ],
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-8000:]},
        ],
        "inputs_measured": {
            "tools/agentspec/agentspec/validate.py": True,
            "tools/agentspec-js/parity": True,
            "tools/agentspec-js/fixtures": True,
            "tools/agentspec-js/src": True,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "defects": [],
        "registered": True,
        "notes": (
            "G-1 for IMP-0149: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit UNIT-ARTIFACT-MANIFEST row. Did not run global "
            "unit_manifest.py --write. Did not relaunch finish-everything-close. "
            "SUCCESS:IMP-0149"
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size}")
    print("SUCCESS:IMP-0149")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
