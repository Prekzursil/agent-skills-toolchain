#!/usr/bin/env python3
"""Run named probes for the 9 assigned envelope IDs on Windows (diagnosis)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\source\ast-integrate")
PROBES = [
    ("ARC-0052", "command-center/p2-wave/probes/ARC-0052/probe1_coverage.py"),
    ("ARC-0052", "command-center/p2-wave/probes/ARC-0052/probe2_error_contract.py"),
    ("ARC-0059", "command-center/p2-wave/probes/ARC-0059/probe1_singularity.py"),
    ("ARC-0059", "command-center/p2-wave/probes/ARC-0059/probe2_provenance.py"),
    ("CC-0002", "command-center/p2-wave/probes/CC-0002/probe1_detector_controls.py"),
    ("CC-0002", "command-center/p2-wave/probes/CC-0002/probe2_reviewer_fifth.py"),
    ("CNF-0140", "command-center/p2-wave/probes/CNF-0140/probe1_known_present.py"),
    ("CNF-0140", "command-center/p2-wave/probes/CNF-0140/probe2_detector_regrade.py"),
    ("CNF-0158", "command-center/p2-wave/probes/CNF-0158/probe1_reproduce.py"),
    ("CNF-0158", "command-center/p2-wave/probes/CNF-0158/probe2_controls.py"),
    ("ARC-0024", "command-center/p2-wave/probes/ARC-0024/probe1_lifecycle.py"),
    ("ARC-0024", "command-center/p2-wave/probes/ARC-0024/probe2_budget.py"),
    ("CNF-0001", "command-center/p2-wave/probes/CNF-0001/probe1_fixture_suite.py"),
    ("CNF-0001", "command-center/p2-wave/probes/CNF-0001/probe2_empty_source_hole.py"),
    ("CNF-0063", "command-center/p2-wave/probes/CNF-0063/probe1_origin_trace.py"),
    ("CNF-0063", "command-center/p2-wave/probes/CNF-0063/probe2_republication.py"),
    ("ARC-0058", "command-center/p2-wave/probes/ARC-0058/probe1_evidence_or_cut.py"),
    ("ARC-0058", "command-center/p2-wave/probes/ARC-0058/probe2_overclaim.py"),
]


def main() -> int:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AST_INTEGRATE_ROOT"] = str(REPO)
    hook = str(REPO / "command-center/p2-wave/seed-stage")
    env["PYTHONPATH"] = os.pathsep.join(
        [
            hook,
            str(REPO),
            str(REPO / "tools"),
            str(REPO / "tools/measure-guard"),
            str(REPO / "platform/lib"),
            str(REPO / "tools/agentspec"),
            env.get("PYTHONPATH", ""),
        ]
    )
    rows = []
    for uid, rel in PROBES:
        print(f"=== {uid} {rel} ===", flush=True)
        try:
            p = subprocess.run(
                [sys.executable, "-B", str(REPO / rel)],
                cwd=str(REPO),
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )
            text = ((p.stdout or "") + (p.stderr or "")).strip()
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc, text = 124, "TIMEOUT"
        tail = "\n".join(text.splitlines()[-12:])
        print(f"rc={rc}")
        print(tail)
        print(flush=True)
        rows.append({"uid": uid, "rel": rel, "rc": rc, "tail": tail[-1500:]})
    out = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/_g1_env9_probes.json"
    import json

    out.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    failed = [r for r in rows if r["rc"] != 0]
    print(f"SUMMARY ok={len(rows)-len(failed)} fail={len(failed)} n={len(rows)}")
    for r in failed:
        print(f" FAIL {r['uid']} {Path(r['rel']).name} rc={r['rc']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
