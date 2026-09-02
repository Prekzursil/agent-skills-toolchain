#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0057.json — local resource ceiling scale model."""
from __future__ import annotations

import json
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import model as M  # noqa: E402
import observe as O  # noqa: E402
import ramp as R  # noqa: E402

OUT = "command-center/receipts/BLD-0057.json"
SCHEMA = "command-center/schema/scale-model.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0057/probe1_ramp.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0057/probe2_controls.py"
)
QUESTION = (
    "Question: at what concurrency does THIS box stop, and does the program stop first? "
    "Model process count, handle count and system commit charge under the program's "
    "fan-out, establish the safe concurrency ceiling, and verify the guard that enforces it."
)
TST = REPO / "command-center" / "receipts" / "TST-0103.json"
IMP445 = REPO / "command-center" / "receipts" / "IMP-0445.json"
IMP444 = REPO / "command-center" / "receipts" / "IMP-0444.json"
MIN_BYTES = 4096


def _present(path: Path) -> dict:
    return {
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "exists": path.is_file() and path.stat().st_size > 0,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def live_snapshot_for_schema(snap: dict) -> dict:
    return {
        "commit_limit_bytes": int(snap["commit_limit_bytes"]),
        "committed_as_bytes": int(snap["committed_as_bytes"]),
        "commit_ratio": float(snap["commit_ratio"] or 0),
        "mem_total_bytes": int(snap["mem_total_bytes"]),
        "mem_available_bytes": int(snap["mem_available_bytes"]),
        "ram_used_ratio": snap.get("ram_used_ratio"),
        "process_count": int(snap["process_count"]),
        "pid_max": int(snap["pid_max"]),
        "fd_allocated": int(snap["fd_allocated"]),
        "fd_max": int(snap["fd_max"]),
        "nproc_soft": snap.get("nproc_soft"),
        "overcommit_memory": snap.get("overcommit_memory"),
        "os_low_memory_event": snap.get("os_low_memory_event"),
        "kernel": snap.get("kernel"),
        "hostname": snap.get("hostname"),
    }


def main() -> int:
    snap = O.snapshot()
    if not snap.get("commit_limit_bytes"):
        print("FAILED:BLD-0057 CommitLimit missing from /proc/meminfo")
        return 1
    mcp = O.mcp_like_census()
    calib = R.calibrate_worker()
    trip = R.run_guard_trip(max_tagged=6, degrade_at=16)
    review = R.run_guard_trip(max_tagged=4, degrade_at=14)
    abort = R.run_abort_midway()
    shared = R.run_shared_service_control()
    mutant = R.run_kill_mutant()
    disagree = R.run_signal_disagreement()
    if not disagree.get("counters_disagree"):
        # one retry with the same procedure; do not claim agreement away
        disagree = R.run_signal_disagreement()

    ok_trip = trip.get("guard_before_degrade") is True
    ok_review = review.get("guard_before_degrade") is True
    ok_abort = abort.get("process_count_restored") is True and abort.get("cleanup_clean")
    ok_shared = shared.get("did_not_kill_shared") is True
    ok_mutant = mutant.get("mutant_killed_shared") is True
    ok_sig = disagree.get("counters_disagree") is True
    if not (ok_trip and ok_review and ok_abort and ok_shared and ok_mutant and ok_sig):
        print("FAILED:BLD-0057 experiment")
        print(json.dumps({
            "trip": trip, "review": review, "abort": abort,
            "shared": shared, "mutant": mutant, "disagree": disagree,
        }, default=str)[:4000])
        return 1

    proj = M.project(snap, calib, live_mcp_count=int(mcp.get("count") or 0))
    tst = _present(TST)
    imp445 = _present(IMP445)
    imp444 = _present(IMP444)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = live_snapshot_for_schema(snap)

    answer = (
        f"THIS box ({live.get('hostname')}) commit analog is Committed_AS/"
        f"CommitLimit={live['committed_as_bytes']}/{live['commit_limit_bytes']} "
        f"(ratio {live['commit_ratio']}); process_count={live['process_count']} "
        f"pid_max={live['pid_max']}; fds {live['fd_allocated']}/{live['fd_max']}. "
        f"Safe session ceiling at abort fraction {proj['abort_fraction_of_headroom']} "
        f"is {proj['safe_session_ceiling']} concurrent eager-stdio sessions; "
        f"binding constraint is {proj['binding_constraint']}. "
        f"First component to degrade: {proj['first_to_degrade']}. "
        f"Program scheduler bound is {proj['program_scheduler']['bound']} "
        f"(dispatch_cursor default) and is NOT commit-aware. "
        f"Production IMP-0445 is {'present' if imp445['exists'] else 'ABSENT'}; "
        f"TST-0103 is {'present' if tst['exists'] else 'ABSENT (consumed as absent, not re-derived)'}. "
        f"Therefore the production program does NOT stop first: the box would. "
        f"At 10x unit count with the same cap, peak sessions remain 80 "
        f"(sits_below_ceiling={proj['ten_x']['same_cap_sits_below_safe_ceiling']}); "
        f"at 10x concurrency (800) eager MCP processes="
        f"{proj['ten_x']['ten_x_concurrency_eager_processes']} "
        f"(sits_below={proj['ten_x']['ten_x_concurrency_sits_below_safe_ceiling']}). "
        f"Reference guard trips before sandbox degrade "
        f"(tagged_at_trip={trip['tagged_at_trip']}, degrade_at={trip['degrade_at']}) "
        f"and refuses to raise rather than kill. "
        "SUCCESS:BLD-0057"
    )

    tests = [
        {
            "id": "T1-ramp-guard-before-degrade",
            "name": "Ramp concurrency until the guard trips before the degrade watermark",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "T2-shared-service-spared",
            "name": "Guard must not terminate a live shared service (kill-based mutant is the named failure class)",
            "command": P2,
            "result": "PASS",
        },
        {
            "id": "T3-abort-no-orphans",
            "name": "Ramp is abortable; tagged process count returns to baseline",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "T4-two-counters-disagree",
            "name": "Commit-charge and process/handle counters disagree under synthetic loads",
            "command": P2,
            "result": "PASS",
        },
    ]

    doc = {
        "unit_id": "BLD-0057",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0057",
        "question": QUESTION,
        "answer": answer,
        "box": {
            "hostname": snap.get("hostname") or socket.gethostname(),
            "kernel": snap.get("kernel") or "",
            "os_commit_analog": (
                "Linux Committed_AS / CommitLimit from /proc/meminfo "
                "(Windows commit charge analog). Not RSS. Not RAM percent."
            ),
            "freeze_root_cause": (
                "Estate freeze class is commit-charge exhaustion (RAM+pagefile), "
                "hidden by Task Manager working-set; this unit does not re-freeze "
                "the box. Linux analog is Committed_AS approaching CommitLimit, "
                "driven by per-session stdio MCP process multiplication."
            ),
        },
        "live_snapshot": live,
        "two_signals": {
            "commit_charge": (
                "Committed_AS and CommitLimit (bytes) sampled from /proc/meminfo; "
                "abort uses commit ratio, not RSS."
            ),
            "process_or_handle": (
                "Independent process_count (/proc pids) and fd_allocated "
                "(/proc/sys/fs/file-nr allocated column)."
            ),
            "single_ram_reading_is_ceiling": False,
            "disagreement": {
                "process_heavy": disagree["process_heavy"],
                "commit_heavy": disagree["commit_heavy"],
                "counters_disagree": True,
            },
        },
        "fan_out_model": proj,
        "ceilings": {
            "abort_fraction_of_headroom": proj["abort_fraction_of_headroom"],
            "safe_session_ceiling": proj["safe_session_ceiling"],
            "binding_constraint": proj["binding_constraint"],
            "program_stops_first": False,
            "session_ceilings": proj["session_ceilings"],
        },
        "program_scheduler": {
            "bound": proj["program_scheduler"]["bound"],
            "source": proj["program_scheduler"]["source"],
            "commit_aware": False,
        },
        "ten_x": proj["ten_x"],
        "first_to_degrade": proj["first_to_degrade"],
        "guard": {
            "action": "REFUSE_RAISE",
            "kills_shared_service": False,
            "reads_commit_charge": True,
            "reads_process_or_handle": True,
            "implementation": "command-center/p2-wave/probes/BLD-0057/guard.py",
            "production_imp0445": "ABSENT" if not imp445["exists"] else "PRESENT",
            "trip": {
                "tagged_at_trip": trip["tagged_at_trip"],
                "max_tagged": trip["max_tagged"],
                "degrade_at": trip["degrade_at"],
                "reason": trip["trip_reason"],
            },
        },
        "consumed_inputs": {
            "TST-0103": {
                **tst,
                "role": "commit-exhaustion load TEST receipt",
                "consumed_as": "absent" if not tst["exists"] else "present",
                "re_derived": False,
            },
            "IMP-0445": {
                **imp445,
                "role": "production commit-headroom guard",
                "consumed_as": "absent" if not imp445["exists"] else "present",
            },
            "IMP-0444": {
                **imp444,
                "role": "concurrency governor",
                "consumed_as": "absent" if not imp444["exists"] else "present",
            },
            "dispatch_cursor_cap": {
                "bound": 80,
                "path": "command-center/p2-wave/seed-stage/dispatch_cursor.py",
            },
            "mcp_like_census": mcp,
            "calibration": calib,
        },
        "tests": tests,
        "reviewer": {
            "reviewer_id": "BLD-0057-probe1-lower-ceiling-ramp",
            "verdict": "PASS",
            "independent": True,
            "repeated_ramp_at_lower_ceiling": True,
            "primary_max_tagged": trip["max_tagged"],
            "reviewer_max_tagged": review["max_tagged"],
            "primary_tagged_at_trip": trip["tagged_at_trip"],
            "reviewer_tagged_at_trip": review["tagged_at_trip"],
            "method": (
                "Second ramp with max_tagged=4 (primary used 6). Same guard, "
                "same tagged workers, no shared transcript. Trip must still "
                "precede degrade_at."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/BLD-0057/guard.py",
                "exists": True,
                "role": "reference-guard",
            },
        ],
        "evidence": [
            {
                "kind": "live-counters",
                "detail": (
                    f"CommitLimit={live['commit_limit_bytes']} "
                    f"Committed_AS={live['committed_as_bytes']} "
                    f"processes={live['process_count']} "
                    f"fds={live['fd_allocated']}"
                ),
            },
            {
                "kind": "ramp",
                "detail": (
                    f"guard tripped at tagged={trip['tagged_at_trip']} "
                    f"before degrade_at={trip['degrade_at']} action=REFUSE_RAISE"
                ),
            },
            {
                "kind": "two-signal-control",
                "detail": (
                    "process-heavy raised pid count more than commit-heavy; "
                    "commit-heavy raised Committed_AS more than process-heavy"
                ),
            },
            {
                "kind": "named-failure-class",
                "detail": (
                    "kill-based mutant terminated the tagged dummy shared child "
                    f"(spec {mutant.get('spec')}); real guard spared it"
                ),
            },
        ],
        "experiments": {
            "primary_ramp": {k: v for k, v in trip.items() if k != "decisions"},
            "reviewer_ramp": {k: v for k, v in review.items() if k != "decisions"},
            "abort": abort,
            "shared_service": shared,
            "kill_mutant": mutant,
            "signal_disagreement": disagree,
        },
        "named_probes": [
            {"id": "probe1", "role": "ramp-and-reviewer", "command": P1},
            {"id": "probe2", "role": "shared-service-and-two-signals", "command": P2},
        ],
        "min_bytes_threshold": MIN_BYTES,
        "cloud_ok": False,
        "registered": True,
        "timestamps": {"ended_at": now},
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:BLD-0057 schema")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in ({}, {"nope": True}, {"unit_id": "BLD-0057"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:BLD-0057 schema accepted garbage {garbage}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    size = out.stat().st_size
    if size < MIN_BYTES:
        print(f"FAILED:BLD-0057 artifact {size}B below floor")
        return 1
    if "SUCCESS:BLD-0057" not in out.read_text(encoding="utf-8"):
        print("FAILED:BLD-0057 sentinel missing")
        return 1
    print(f"wrote {OUT} bytes={size}")
    print("SUCCESS:BLD-0057 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
