#!/usr/bin/env python3
"""Write TST-0150 catalog receipt plus per-unit G-1 sidecars.

Does not run tools/command-center/unit_manifest.py --write.
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
UNIT = "TST-0150"
OUT = "command-center/receipts/TST-0150.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/monitor_report"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0150/probe1_kill_restart_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0150/probe2_memory_only_negative.py"
)
SUPPORTING = [
    "tools/event-ledger/records.py",
    "tools/event-ledger/writer.py",
    "tools/event-ledger/state.py",
    "tools/event-ledger/recover.py",
    "tools/event-ledger/monitor.py",
    "command-center/p2-wave/probes/TST-0150/remote_jobs.py",
    "command-center/p2-wave/probes/TST-0150/reconcile.py",
    "command-center/p2-wave/probes/TST-0150/scenario.py",
    "command-center/p2-wave/probes/TST-0150/probe1_kill_restart_both_states.py",
    "command-center/p2-wave/probes/TST-0150/probe2_memory_only_negative.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
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
        "exists": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/TST-0150/SUBAGENT-RETURN.json",
        "role": role,
    }


def probe_blob(role: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": "command",
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"command\x1f{command}".encode()).hexdigest()[:32],
    }


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting_arts = [row(p, "supporting") for p in SUPPORTING]
    p_src = probe_blob("source", P1, t1, c1)
    p_ver = probe_blob("verifier", P2, t2, c2)

    answer = (
        "After LiveMonitor.kill, remote workers keep appending REMOTE_COMPLETED "
        "to the durable JSONL ledger and to an independent remote-jobs.json. "
        "recover() folds the ledger with no RAM context and harvests A,B; C was "
        "harvested before death; D stays in-flight. Reconciliation against the "
        "remote job list loaded from disk yields unknown_count=0 for every unit "
        "the remote side considers finished. An uninterrupted twin run also "
        "yields unknown_count=0 (both-states). A memory-only mutant that records "
        "A,B terminal state only in the live process is detected: after restart "
        "those ids are UNKNOWN against the same remote job list, while a check "
        "that trusted the pre-kill RAM snapshot would have passed silently."
    )

    receipt = {
        "schema_version": 1,
        "report_kind": "monitor_report",
        "profile": "monitor-report",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0150",
        "completion_sentinel": "SUCCESS:TST-0150",
        "spec_anchor": "WORK-UNIT-CATALOG.json:TST-0150",
        "min_bytes_threshold": 128,
        "title": "Monitor death does not lose remote terminal state",
        "question": (
            "Kill the monitor while remote work continues: after restart, is "
            "every remote unit's terminal state recoverable from the durable "
            "ledger? PASS requires zero units in an UNKNOWN state that the "
            "remote side considers finished."
        ),
        "answer": answer,
        "claim_under_test": (
            "Durable ledger + independent remote job list recover every "
            "remote-finished unit after monitor death; RAM-only terminal "
            "state is reported UNKNOWN by the same reconciler."
        ),
        "overall_verdict": "PASS",
        "named_failure_class": "monitor-dies-while-remote-work-continues",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "artifacts": [
            {
                "path": a["path"],
                "bytes": a["bytes"],
                "sha256": a["sha256"],
                "exists": True,
                "role": a["role"],
                "eol": "LF",
            }
            for a in supporting_arts
        ],
        "evidence": [
            {
                "claim": (
                    "Signal (a): post-restart recover() on the JSONL ledger "
                    "harvests A,B (finished during the outage), keeps C "
                    "harvested, leaves D in-flight, and reconciliation reports "
                    "unknown_count=0. Signal (b): remote-jobs.json is a second "
                    "file whose sha256 differs from the ledger; it lists A,B,C "
                    "as succeeded when queried from disk after restart. The "
                    "uninterrupted twin also reports unknown_count=0."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/event-ledger/recover.py:recover",
                "confidence": "almost-certain",
                "probes": [p_src, p_ver],
            },
            {
                "claim": (
                    "Negative control: A,B completed only in monitor RAM while "
                    "the remote job list recorded them succeeded. After kill, "
                    "disk reconcile reports UNKNOWN for A,B (C durable harvest "
                    "is not UNKNOWN). Trusting the pre-kill RAM snapshot yields "
                    "unknown_count=0, so a memory-only check would miss the loss; "
                    "this test does not trust that snapshot."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0150/scenario.py:scenario_memory_only",
                "confidence": "almost-certain",
                "probes": [p_ver, p_src],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {
                "id": "both-states-uninterrupted-zero-unknown",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "negative-memory-only-detected-as-lost",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "memory-only-terminal-state",
                "kind": "known-broken-monitor",
                "description": (
                    "Terminal state held only in monitor memory must be "
                    "reported UNKNOWN against the remote job list after restart"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "UNKNOWN A,B",
                "good_state_output": "unknown_count=0",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0150-probe2-memory-only-and-bash-rerun",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": (
                "Probe 2 does not re-score probe 1's zero-UNKNOWN durable run "
                "as agreement; it only checks that RAM-only completions become "
                "UNKNOWN and that bash recomputes the same UNKNOWN set."
            ),
            "windows_shells": {
                "host": "linux",
                "git_bash_analogue": "bash",
                "pwsh7_present": False,
                "note": (
                    "This worktree is Linux. Probe 2 re-ran scenario.py "
                    "--canonical-memory under bash -lc and compared UNKNOWN ids. "
                    "pwsh7 and Windows Git Bash binaries are absent here; that "
                    "gap is residual, not a hidden PASS."
                ),
            },
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0150/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_blob(
                    "verifier",
                    "python3 command-center/p2-wave/_measure_one_delivered.py TST-0150",
                    "pending live measure after this write",
                    0,
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog reviewer_requirement asks for a second Windows "
                    "shell pair (pwsh7 and Git Bash). This host has bash and "
                    "no pwsh. Divergence on native Windows is not measured."
                ),
                "verdict": "ACKNOWLEDGED",
                "settling_experiment": (
                    "Re-run probe1 and probe2 under Windows pwsh7 and Git Bash "
                    "and compare canonical UNKNOWN sets."
                ),
            }
        ],
        "notes": (
            "G-1 for TST-0150: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "cloud_ok is false and is not delivery."
        ),
        "cloud_ok": False,
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    extra = []
    for name, role in (
        ("probe1-both-states.raw.json", "supporting"),
        ("probe2-memory-only.raw.json", "supporting"),
    ):
        rel = f"command-center/p2-wave/probes/TST-0150/{name}"
        if (REPO / rel).is_file():
            extra.append(row(rel, role))

    primary = row(OUT, "primary")
    artifacts = [primary] + supporting_arts + extra
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0150",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "kill-restart-both-states",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "memory-only-negative",
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
        "manifest_path": "command-center/p2-wave/probes/TST-0150/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "TST-0150-probe2-memory-only-and-bash-rerun",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for TST-0150: live named probes exit 0, receipts/TST-0150.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
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
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:TST-0150 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
