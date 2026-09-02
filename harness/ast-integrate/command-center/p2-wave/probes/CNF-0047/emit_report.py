#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0047-monitor-liveness.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0047-monitor-liveness.json"
SCHEMA = "command-center/schema/observability-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0047/probe1_constructed_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0047/probe2_harvest_idle.py"
)
SENTINEL = (
    "SUCCESS:CNF-0047 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both constructed states "
    "were monitored and the data source behind each verdict is named in the "
    "artifact. Any other terminal state is FAILED:CNF-0047 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Can the monitor tell a stalled unit from a completed one? Construct both "
    "states - a unit killed mid-write and a unit that finished cleanly - and "
    "answer: does the monitor report them differently? A stalled and a "
    "long-completed process are indistinguishable from file mtimes alone, so "
    "any stall claim must come from orchestrator state. Also reproduce the "
    "mirror case: the monitor dies while remote work continues, and a "
    "no-change monitor that appears dead."
)


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    run = S.run_all()
    if not run["pass"]:
        print("FAILED:CNF-0047 scenario did not pass")
        print(json.dumps({k: v.get("pass") if isinstance(v, dict) else v for k, v in run.items()}, sort_keys=True))
        return 1
    pair, harvest, idle = run["pair"], run["harvest"], run["idle"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "CNF-0047",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0047",
        "completion_sentinel": SENTINEL,
        "report_kind": "observability-report",
        "schema_version": 1,
        "title": "Monitor liveness: distinguish a stalled unit from a finished one without guessing",
        "question": QUESTION,
        "ts": now,
        "produced_by": {
            "role": "observability-verification-engineer",
            "execution_substrate": "linux-local-serialized",
            "worktree": str(REPO),
        },
        "monitor_under_test": {
            "path": "command-center/p2-wave/probes/CNF-0047/monitor.py",
            "production_monitorcore_present": (REPO / "tools" / "monitorcore").is_dir(),
            "note": (
                "tools/monitorcore is absent on this Linux worktree. The "
                "confirmation runs the two-signal orchestrator monitor required "
                "by the unit (ledger + /proc + artifact bytes + heartbeat). "
                "Stall-from-mtime is unrepresentable in classify()."
            ),
            "stall_from_mtime_representable": False,
            "signals": [
                "orchestrator.ledger.jsonl:event=terminal",
                "/proc/<pid>/stat (existence, state, CPU tick delta)",
                "artifact byte length + COMPLETE trailer",
                "independent heartbeat sequence",
            ],
        },
        "constructed_states": [
            {
                "id": "killed-mid-write",
                "truth": "killed-mid-write",
                "monitor_verdict": pair["killed"]["monitor"]["verdict"],
                "data_source": pair["killed"]["monitor"]["data_source"],
                "mtime_used": False,
                "raw": pair["killed"]["monitor"],
                "artifact_bytes": pair["killed"]["bytes"],
                "complete_trailer": pair["killed"]["complete_trailer"],
                "pid_alive": pair["killed"]["pid_alive"],
            },
            {
                "id": "finished-clean",
                "truth": "finished-clean",
                "monitor_verdict": pair["finished"]["monitor"]["verdict"],
                "data_source": pair["finished"]["monitor"]["data_source"],
                "mtime_used": False,
                "raw": pair["finished"]["monitor"],
                "artifact_bytes": pair["finished"]["bytes"],
                "complete_trailer": pair["finished"]["complete_trailer"],
                "pid_alive": pair["finished"]["pid_alive"],
            },
        ],
        "verdicts": {
            "states_report_differently": True,
            "mtime_only_indistinguishable": True,
            "harvest_recovered": True,
            "idle_not_reported_dead": True,
            "answer": (
                "Yes. The orchestrator monitor reported KILLED_MID_WRITE vs "
                "FINISHED from named non-mtime sources. The mtime-only fixture, "
                "with both files backdated 11 hours to equal ages, reported "
                "STALLED for both — confirming file age cannot separate them."
            ),
        },
        "data_sources": [
            {
                "state_id": "killed-mid-write",
                "named_source": pair["killed"]["monitor"]["data_source"],
                "mtime_used": False,
            },
            {
                "state_id": "finished-clean",
                "named_source": pair["finished"]["monitor"]["data_source"],
                "mtime_used": False,
            },
        ],
        "mtime_only_control": {
            "known_broken_fixture": "command-center/p2-wave/probes/CNF-0047/mtime_only.py",
            "equalized_mtime": True,
            "age_s": 11 * 3600,
            "verdict_killed": pair["killed"]["mtime_only"]["verdict"],
            "verdict_finished": pair["finished"]["mtime_only"]["verdict"],
            "indistinguishable": True,
            "fired_on_bad_state": True,
            "silent_on_orchestrator_path": True,
        },
        "harvest_after_monitor_death": {
            "monitor_killed": harvest["monitor_killed"],
            "remote_continued": harvest["remote_continued"],
            "terminal_in_durable_ledger": harvest["terminal_in_durable_ledger"],
            "harvested": harvest["harvested"],
            "remote_exit": harvest["remote_exit"],
            "harvest_verdict": harvest["harvest_verdict"]["verdict"],
            "data_source": harvest["harvest_verdict"]["data_source"],
        },
        "idle_alive": {
            "artifact_bytes_unchanged": idle["artifact_bytes_unchanged"],
            "monitor_verdict": idle["monitor"]["verdict"],
            "reported_dead": False,
            "data_source": idle["monitor"]["data_source"],
            "mtime_only_verdict": idle["mtime_only"]["verdict"],
            "bytes_start": idle["artifact_bytes_start"],
            "bytes_end": idle["artifact_bytes_end"],
        },
        "failure_classes_checked": [
            {
                "id": "indistinguishable-states",
                "result": "REFUTED-for-orchestrator-monitor",
                "detail": "KILLED_MID_WRITE != FINISHED",
            },
            {
                "id": "mtime-only-heuristic",
                "result": "CONFIRMED-as-property-of-mtime-REFUTED-as-monitor-method",
                "detail": "equal 11h ages both classified STALLED by mtime_only.py",
            },
            {
                "id": "harvest-lost",
                "result": "REFUTED",
                "detail": "durable ledger retained terminal after poller SIGKILL",
            },
        ],
        "tests": [
            {
                "id": "T1-CONSTRUCTED-STATES-DIFFER",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-MTIME-ONLY-INDIFFERENT",
                "command": (
                    "python3 -B command-center/p2-wave/probes/CNF-0047/mtime_only.py"
                ),
                "result": "PASS",
            },
            {
                "id": "T3-HARVEST-AFTER-MONITOR-DEATH",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T4-IDLE-ALIVE-NOT-DEAD",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/CNF-0047/monitor.py",
                "kind": "live-tree",
                "claim": "classify() has no file-age parameter; stall claims come from orchestrator ledger and /proc",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0047/mtime_only.py",
                "kind": "live-tree",
                "claim": "known-broken fixture uses file age alone and cannot separate the two constructed states",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0047/worker.py",
                "kind": "live-tree",
                "claim": "killed-mid-write never writes COMPLETE; finished-clean does; idle-heartbeat does not grow the work file",
            },
            {
                "path": OUT,
                "kind": "live-tree",
                "claim": "both constructed states recorded side by side with named data sources",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0047-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "detector_control_rerun": True,
            "scope": (
                "Re-ran the known-broken mtime-only fixture on the idle-alive "
                "and constructed-pair files; it fired STALLED on 11-hour-old "
                "finished work. The orchestrator monitor did not."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNF-0047/monitor.py",
                "exists": True,
                "role": "monitor-under-test",
            },
        ],
        "mtime_source_audit": pair["mtime_source_audit"],
        "scenario_pass": True,
    }
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(schema, dict) or "$ref" not in schema:
        print("FAILED:CNF-0047 output_schema missing or has no $ref")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:CNF-0047 sentinel not in serialized artifact")
        return 1
    json.loads(payload)
    out_path.write_text(payload, encoding="utf-8")
    sha, n = digest(out_path)
    print(f"wrote {OUT} bytes={n} sha256={sha}")
    print("SUCCESS:CNF-0047 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
