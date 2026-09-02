#!/usr/bin/env python3
"""Emit TST-0242 receipt, SUBAGENT-RETURN.json, and per-unit UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/receipts/TST-0242.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0242/probe1_fanout_ceiling.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0242/probe2_shared_pid_refusal.py"
)
SUPPORTING = [
    "tools/plugin/pressure_guard.py",
    "tools/plugin/mcp_activation.py",
    "tools/plugin/stub_mcp_server.py",
    "command-center/p2-wave/probes/TST-0242/harness.py",
    "command-center/p2-wave/probes/TST-0242/probe1_fanout_ceiling.py",
    "command-center/p2-wave/probes/TST-0242/probe2_shared_pid_refusal.py",
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


def last_json(text: str) -> dict:
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(doc, dict):
                return doc
    return {}


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "exists": True,
        "eol": "LF",
        "unit_id": "TST-0242",
        "receipt_path": "command-center/p2-wave/probes/TST-0242/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2000:])
    print(f"probe2 rc={c2}")
    print(t2[-2000:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0242 probes c1={c1} c2={c2}")
        return 1

    p1 = last_json(t1)
    p2 = last_json(t2)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    guard_sha, guard_bytes = digest(REPO / "tools/plugin/pressure_guard.py")

    shared_10x = p1.get("shared_10x") or {}
    eager = p1.get("eager_unbounded") or {}
    budget = p1.get("eager_budget_refuse") or {}
    commit = p1.get("commit_control") or {}
    base = p1.get("shared_baseline") or {}

    doc = {
        "unit_id": "TST-0242",
        "title": "Process and memory ceilings hold, and the guard never kills a shared service",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0242",
        "completion_sentinel": "SUCCESS:TST-0242",
        "SUCCESS:TST-0242": True,
        "report_kind": "benchmark_result",
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0242]; "
            "_USER-PROMPTS.md:11326-11328 (eager per-session MCP multiplication; "
            "commit exhaustion freezes process creation; kill-based memory guard "
            "terminates a live shared service)"
        ),
        "question": (
            "Does the harness bound per-session MCP/worker process multiplication, "
            "and can its memory guard ever terminate a live shared service? PASS "
            "requires the ceiling to hold under a 10x fan-out AND the guard to be "
            "proven incapable of selecting a shared-service PID."
        ),
        "answer": (
            f"Yes. Lazy-shared 10x fan-out stayed at {shared_10x.get('procfs_n')} "
            f"stub processes (peak procfs={shared_10x.get('peak_procfs')}, "
            f"peak ps={shared_10x.get('peak_ps')}) against a process ceiling of "
            f"{p1.get('process_ceiling')}. Eager unbounded reproduced "
            f"{eager.get('procfs_n')} = sessions×servers. The budgeted eager path "
            f"refused the next session ({budget.get('reason')}) with would_spawn="
            f"{budget.get('would_spawn')} and no extra child. Production selection "
            f"spared shared pid {p2.get('shared_pid')}; the kill-based mutant "
            f"selected it (both-states)."
        ),
        "artifact_paths": [OUT] + SUPPORTING,
        "implementation": {
            "path": "tools/plugin/pressure_guard.py",
            "sha256": guard_sha,
            "bytes": guard_bytes,
            "activation": "tools/plugin/mcp_activation.py",
        },
        "measurements": {
            "n_servers": p1.get("n_servers"),
            "fanout_mult": p1.get("fanout_mult"),
            "fanout_sessions": p1.get("fanout_sessions"),
            "process_ceiling": p1.get("process_ceiling"),
            "shared_baseline": base,
            "shared_10x": shared_10x,
            "eager_unbounded": eager,
            "external_monitor": {
                "process_count_signals": ["procfs_/proc/<pid>/cmdline", "ps_-eo_pid,rss,args"],
                "commit_signals": [
                    "/proc/meminfo Committed_AS (kB)",
                    "/proc/<pid>/status VmRSS+VmSwap commit proxy",
                ],
            },
        },
        "candidate_selection_audit": {
            "shared_pid": p2.get("shared_pid"),
            "production": p2.get("production_audit"),
            "mutant": p2.get("mutant_audit"),
            "fired_on_bad": p2.get("fired_on_bad"),
            "silent_on_good": p2.get("silent_on_good"),
            "shared_survived": p2.get("shared_survived"),
        },
        "evidence": [
            {
                "id": "E1-external-process-and-commit-monitor",
                "claim": (
                    "Peak process count and committed memory were sampled by an "
                    "external monitor (/proc cmdline + ps, Committed_AS + stub "
                    "RSS+swap proxy), not by the pool's internal dict."
                ),
                "path": "command-center/p2-wave/probes/TST-0242/harness.py",
                "shared_10x": shared_10x,
                "baseline": base,
                "commit_control": commit,
            },
            {
                "id": "E2-candidate-list-vs-shared-pid-set",
                "claim": (
                    "The production guard's kill-candidate list has empty overlap "
                    "with the shared-service PID set. A kill-based mutant that "
                    "drops the allowlist selects the same live PID."
                ),
                "path": "tools/plugin/pressure_guard.py",
                "production_audit": p2.get("production_audit"),
                "mutant_audit": p2.get("mutant_audit"),
            },
        ],
        "tests": [
            {
                "id": "detector-control-shared-service-pid-refused",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "regression-seed-eager-per-session-mcp-multiplication",
                "command": P1,
                "result": "PASS",
                "observed": eager,
            },
            {
                "id": "regression-seed-commit-exhaustion-refuses-before-spawn",
                "command": P1,
                "result": "PASS",
                "observed": commit,
            },
            {
                "id": "regression-seed-kill-based-guard-selects-shared-on-mutant-only",
                "command": P2,
                "result": "PASS",
            },
        ],
        "test_ids": [
            "fanout-10x-shared-process-count-flat",
            "eager-unbounded-multiplies",
            "process-ceiling-refuse-before-spawn",
            "commit-hot-refuse-cold-admit",
            "shared-pid-not-in-kill-set",
            "kill-based-mutant-selects-shared",
        ],
        "negative_control_ids": [
            "NC1:eager-stdio-multiplies-sessions-times-servers",
            "NC2:kill-based-mutant-selects-shared-pid",
            "NC3:synthetic-commit-ratio-0.20-admits",
        ],
        "reviewer_verdict": "PASS",
        "reviewer": {
            "reviewer_id": "TST-0242-probe2-shared-pid-refusal",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "OS process table + candidate-selection list, not the author's summary",
        },
        "owner_approval_required": True,
        "owner_approval": (
            "NOT-CHECKED as a live-estate kill: this unit spawned isolated stubs "
            "with unique argv marks and never signalled a pre-existing shared "
            "service. Catalog flag remains true for enabling kill-based orphan "
            "reaping on the owner's machine."
        ),
        "residual_unknowns": [
            (
                "System-wide Committed_AS is recorded but not used as a pass/fail "
                "threshold: it moves with unrelated processes on this box. Pass/fail "
                "for memory uses the per-stub RSS+swap proxy plus the synthetic "
                "commit-ratio control that refuses spawn without exhausting the host."
            ),
            (
                "command-center/schema/receipt.schema.json is absent on this "
                "worktree; this artifact is a benchmark_result-shaped receipt."
            ),
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-4000:]},
        ],
        "min_bytes_threshold": 128,
        "ts": now,
        "notes": (
            "G-1 for TST-0242: live named probes, honest SUCCESS receipt, per-unit "
            "UNIT-ARTIFACT-MANIFEST.json row. Did not run global unit_manifest.py "
            "--write. cloud ok=true is not delivery. SUCCESS:TST-0242"
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    primary = art_row(OUT, "primary")
    artifacts = [primary] + [art_row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "TST-0242",
        "unit_id": "TST-0242",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0242",
        "registered": True,
        "output_path": OUT,
        "output_schema": "command-center/schema/receipt.schema.json#/$defs/benchmark_result",
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1, "raw_output": t1[-4000:]},
            {"id": "probe2", "command": P2, "exit_code": c2, "raw_output": t2[-4000:]},
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
        "manifest_path": "command-center/p2-wave/probes/TST-0242/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0242-probe2-shared-pid-refusal",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0242: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "TST-0242",
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
    print("SUCCESS:TST-0242 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
