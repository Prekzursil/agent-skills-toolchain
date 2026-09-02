#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0103.json (fault-injection receipt)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from checks import probe1_live, probe2_live  # noqa: E402
from commit import host_meta  # noqa: E402

OUT = "command-center/receipts/TST-0103.json"
SCHEMA = "command-center/p2-wave/probes/TST-0103/fault-injection-receipt.schema.json"
CATALOG_SCHEMA = "command-center/schema/fault-injection-receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0103/probe1_guard_sheds_before_process_creation_fails.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0103/probe2_commit_charge_not_working_set.py"
)
QUESTION = (
    "Failure class :11327. Measured root cause on this box: the freeze is "
    "COMMIT charge (RAM+pagefile) exhaustion, not RAM OOM - Task Manager hides "
    "it and Event 2004 is the smoking gun. Target: a load test that drives "
    "commit charge toward the limit and asserts the guard sheds load BEFORE "
    "process creation fails, plus a probe that reads commit charge rather "
    "than working set."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    ramp, e1 = probe1_live()
    ws, e2 = probe2_live()
    errors = e1 + e2
    if errors:
        print("FAILED:TST-0103 emit checks")
        for e in errors:
            print(" ", e)
        return 1

    host = host_meta()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    shed = (ramp.get("guarded") or {}).get("shed") or {}
    fail = (ramp.get("unguarded") or {}).get("fail") or {}
    ord_ = ramp.get("ordering") or {}

    doc = {
        "unit_id": "TST-0103",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0103",
        "title": "Commit-exhaustion guard: process creation freezes before RAM is exhausted",
        "question": QUESTION,
        "failure_class": "commit-exhaustion-process-creation-freeze",
        "report_kind": "fault-injection-receipt",
        "phase": "10",
        "ts": now,
        "injected_fault": {
            "id": "FC-11327",
            "description": (
                "Drive synthetic commit charge toward a commit_limit until "
                "process creation would fail (Windows Event 2004 class). The "
                "host is not driven to freeze; the kernel is in-process."
            ),
            "method": (
                "simulated-commit-kernel plus live /proc/meminfo binding and "
                "untouched anonymous mmap (commit vs RSS divergence)"
            ),
        },
        "host": {
            "os": host["os"],
            "commit_probe_source": host["commit_probe_source"],
            "available_commit_source": host["available_commit_source"],
            "working_set_source": host["working_set_source"],
            "overcommit_memory": host["overcommit_memory"],
            "overcommit_ratio": host["overcommit_ratio"],
            "live_commit_charge_bytes": host["commit_charge_bytes"],
            "live_available_commit_bytes": host["available_commit_bytes"],
            "live_commit_limit_bytes": host["commit_limit_bytes"],
            "live_working_set_bytes": host["working_set_bytes"],
            "live_ram_total_bytes": host["ram_total_bytes"],
            "windows_event_2004": host["windows_event_2004"],
            "note": host["note"],
        },
        "counters_sampled": [
            {
                "name": "commit_charge",
                "source": "Committed_AS (synthetic kernel + /proc/meminfo)",
                "at_shed_bytes": shed.get("commit_charge"),
                "at_fail_bytes": fail.get("commit_charge"),
            },
            {
                "name": "available_commit",
                "source": "CommitLimit - Committed_AS",
                "at_shed_bytes": shed.get("available_commit"),
                "at_fail_bytes": fail.get("available_commit"),
            },
        ],
        "shed_load": {
            "logical_step": ord_.get("shed_step"),
            "logical_ts_ns": ord_.get("shed_logical_ts_ns"),
            "ts_utc": now,
            "commit_charge_bytes": shed.get("commit_charge"),
            "available_commit_bytes": shed.get("available_commit"),
            "rescue_spawn_succeeded": shed.get("rescue_spawn_succeeded"),
            "before_first_process_creation_failure": ord_.get("shed_before_fail"),
        },
        "process_creation_failure": {
            "logical_step": ord_.get("fail_step"),
            "logical_ts_ns": ord_.get("fail_logical_ts_ns"),
            "event": fail.get("event"),
            "commit_charge_bytes": fail.get("commit_charge"),
            "available_commit_bytes": fail.get("available_commit"),
            "observed_on": "unguarded-control-ramp",
        },
        "ramp": ramp,
        "working_set_control": {
            "silent_in_commit_exhaustion": (ws.get("failing_state") or {}).get(
                "working_set_guard_silent"
            ),
            "fires_on_ram_pressure": (ws.get("ram_pressure_state") or {}).get(
                "working_set_guard_fired"
            ),
            "mmap": ws.get("mmap"),
        },
        "parser_binding": {
            "commit_field": "Committed_AS",
            "available_commit_derivation": "CommitLimit - Committed_AS",
            "working_set_field": "Active",
            "live": ws.get("parser_binding"),
        },
        "owner_approval_required": True,
        "owner_signoff": {
            "recorded": False,
            "path": "command-center/OWNER-DECISIONS.md",
            "note": (
                "Catalog requires owner sign-off before program close. G-1 "
                "delivery records the gap; it does not invent a signature."
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "On the same spawn schedule, the commit-charge guard sheds "
                    "and a rescue spawn still succeeds before unguarded process "
                    "creation fails at commit_limit."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0103/ramp.py",
            },
            {
                "id": "C2",
                "claim": (
                    "The guard and live probe read commit_charge "
                    "(Committed_AS) and available_commit, not working set "
                    "(Active/VmRSS). A working-set guard is silent in the "
                    "commit-exhaustion failing state."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0103/guard.py",
            },
            {
                "id": "C3",
                "claim": (
                    "The load test does not drive this host to its real "
                    "commit ceiling. Host freeze is refused; evidence is the "
                    "simulated kernel plus a 64MiB untouched mmap."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0103/commit.py",
            },
        ],
        "tests": [
            {
                "id": "test_guard_sheds_load_before_process_creation_fails",
                "name": "Guard sheds before process creation fails",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_probe_reads_commit_charge_not_working_set",
                "name": "Probe reads commit charge; working-set probe is silent in the failing state",
                "command": P2,
                "result": "PASS",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "shed-before-process-creation-fail", "command": P1},
            {"id": "probe2", "role": "commit-charge-not-working-set", "command": P2},
        ],
        "reviewer": {
            "reviewer_id": "TST-0103-probe2-working-set-silence",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe 2 is mechanically different: both-states fixtures, "
                "meminfo field binding, live mmap divergence, source inspect."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": CATALOG_SCHEMA,
                "exists": True,
                "role": "catalog-schema-path",
                "note": (
                    "Catalog names this path; on this worktree the file is "
                    "currently TST-0004-scoped (const unit_id). TST-0103 "
                    "validates against the unit-local schema instead of "
                    "clobbering that shared file."
                ),
            },
        ],
        "evidence": [
            {
                "kind": "ramp-counters",
                "path": "command-center/p2-wave/probes/TST-0103/ramp.py",
                "note": "commit_charge and available_commit sampled each pre-spawn step",
            },
            {
                "kind": "live-meminfo",
                "path": "/proc/meminfo",
                "note": "Committed_AS vs Active vs CommitLimit on this Linux worktree",
            },
            {
                "kind": "mmap-divergence",
                "path": "command-center/p2-wave/probes/TST-0103/commit.py",
                "note": "untouched anonymous mmap moves commit, not RSS",
            },
        ],
        "headline": (
            f"shed_step={ord_.get('shed_step')} fail_step={ord_.get('fail_step')} "
            f"rescue={ord_.get('guarded_rescue_spawn_succeeded')} "
            f"ws_silent={(ws.get('failing_state') or {}).get('working_set_guard_silent')}"
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0103 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            print(f"FAILED:TST-0103 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(doc["headline"])
    print("SUCCESS:TST-0103")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
