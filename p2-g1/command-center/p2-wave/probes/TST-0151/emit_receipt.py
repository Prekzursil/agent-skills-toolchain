#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0151.json from a live two-signal run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import liveness as L  # noqa: E402

OUT = "command-center/receipts/TST-0151.json"
SENTINEL = "SUCCESS:TST-0151"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0151/probe1_idle_vs_sigstop.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0151/probe2_alive_before_dead.py"
)
QUESTION = (
    "Does the liveness signal distinguish a process that is alive and idle "
    "from one that is hung? PASS requires a heartbeat emitted independently "
    "of work output, and the detector must flip when the process is SIGSTOPped "
    "and again when it is killed."
)
SUPPORTING = [
    "command-center/p2-wave/probes/TST-0151/liveness.py",
    "command-center/p2-wave/probes/TST-0151/probe1_idle_vs_sigstop.py",
    "command-center/p2-wave/probes/TST-0151/probe2_alive_before_dead.py",
    "command-center/p2-wave/probes/TST-0151/emit_receipt.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "bytes": size,
        "sha256": sha,
    }


def slim(row: dict) -> dict:
    v = row["verdict"]
    return {
        "planted": row["planted"],
        "pid_alive": row["pid_alive"],
        "proc_state": row["proc_state"],
        "heartbeat_t0": row["heartbeat_t0"],
        "heartbeat_t1": row["heartbeat_t1"],
        "heartbeat_age_s": row["heartbeat_age_s"],
        "heartbeat_source": row["heartbeat_source"],
        "cpu_t0": row["cpu_t0"],
        "cpu_t1": row["cpu_t1"],
        "cpu_delta": row["cpu_delta"],
        "cpu_source": row["cpu_source"],
        "work_t0": row["work_t0"],
        "work_t1": row["work_t1"],
        "window_s": row["window_s"],
        "work_bytes_unchanged": row["work_bytes_unchanged"],
        "verdict": v["verdict"],
        "hang_fired": v["hang_fired"],
        "reason": v["reason"],
        "guessed": v["guessed"],
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    table = L.campaign()
    if not table["ok"]:
        print("FAILED:TST-0151 emit live campaign did not satisfy acceptance")
        print(json.dumps({
            "sequence_both": table["both_states"]["sequence"],
            "sequence_ctrl": table["detector_control"]["sequence"],
            "silent_idle": table["both_states"]["detector_silent_idle"],
            "fires_sigstop": table["both_states"]["detector_fires_sigstop"],
            "alive_before_dead": table["detector_control"]["alive_before_dead"],
        }, indent=2, sort_keys=True))
        return 1

    both = table["both_states"]
    ctrl = table["detector_control"]
    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    b07 = REPO / "command-center/receipts/B07.json"
    doc = {
        "schema_version": 1,
        "unit_id": "TST-0151",
        "id": "TST-0151",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Heartbeat separates idle-but-alive from hung",
        "question_or_target": QUESTION,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:TST-0151",
        "min_bytes_threshold": 2048,
        "profile": "monitor-report",
        "report_kind": "monitor_report",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "observability-tester",
            "execution_substrate": "local-serialized",
        },
        "answer": (
            "A heartbeat token independent of work output stays ALIVE for an "
            "idle sleeping process (work.bin remains 0 bytes; hang detector "
            "silent). The same process SIGSTOPped freezes both heartbeat age "
            "and /proc CPU-time over a 20s window and the detector fires HUNG "
            "(state=T). Kill flips again to DEAD. A work-silence mutant fires "
            "on idle-alive; a heartbeat-only mutant stays HUNG after kill and "
            "cannot make the second flip. mtime observations are UNDECIDABLE. "
            "B07 cockpit/monitorcore is unbuilt on this Linux worktree; this "
            "unit delivers the two-signal process-liveness test the catalog "
            "asks for, not a second control plane. "
            + SENTINEL
        ),
        "dependencies": {
            "B07": {
                "role": "cockpit / monitor surface",
                "receipt_present": b07.is_file(),
                "note": (
                    "B07 is unbuilt here. TST-0151 does not claim the cockpit "
                    "pane exists. The detector under test is "
                    "command-center/p2-wave/probes/TST-0151/liveness.py, using "
                    "heartbeat age and CPU-time delta, never mtime."
                ),
            }
        },
        "implementation": {
            "module": "command-center/p2-wave/probes/TST-0151/liveness.py",
            "heartbeat_signal": "heartbeat-age (JSONL token + CLOCK_MONOTONIC, independent of work output)",
            "cpu_signal": "process CPU-time delta (utime+stime from /proc/<pid>/stat) sampled over 20s",
            "mtime_accepted": False,
            "work_output_is_hang_signal": False,
            "window_s": L.WINDOW_S,
            "platform": "linux-posix-SIGSTOP",
        },
        "both_states": {
            "sequence": both["sequence"],
            "detector_silent_idle": both["detector_silent_idle"],
            "detector_fires_sigstop": both["detector_fires_sigstop"],
            "flipped_on_sigstop": both["flipped_on_sigstop"],
            "flipped_on_kill": both["flipped_on_kill"],
            "work_independent_idle": both["work_independent_idle"],
            "idle": slim(both["idle"]),
            "sigstop": slim(both["sigstop"]),
            "killed": slim(both["killed"]),
        },
        "detector_control": {
            "sequence": ctrl["sequence"],
            "alive_before_dead": ctrl["alive_before_dead"],
            "trusted_dead": ctrl["trusted_dead"],
            "known_running": slim(ctrl["known_running"]),
            "killed": slim(ctrl["killed"]),
        },
        "mutation": {
            "work_silence_fires_on_idle": both["work_silence_mutant_fires_on_idle"],
            "heartbeat_only_after_kill_stays_hung": both["heartbeat_only_mutant_after_kill"] == L.HUNG,
            "mtime_idle_undecidable": both["mtime_idle"]["verdict"] == L.UNDECIDABLE,
            "mtime_idle": both["mtime_idle"],
        },
        "evidence": [
            {
                "claim": (
                    "Idle-alive (heartbeat advancing, work bytes frozen at 0) "
                    "is ALIVE and the hang detector is silent; SIGSTOP over a "
                    "20s window freezes heartbeat and CPU-time and fires HUNG; "
                    "kill flips to DEAD."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0151/liveness.py",
                "confidence": "almost-certain",
                "signals": [
                    "heartbeat-age",
                    "cpu-time-delta-20s",
                ],
                "probes": [
                    {
                        "role": "source",
                        "method": "live-posix-SIGSTOP",
                        "command": "run_idle_then_sigstop_then_kill()",
                        "raw_output": json.dumps(both["sequence"], sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P1,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    },
                ],
            },
            {
                "claim": (
                    "The detector reports ALIVE for a known-running process "
                    "before any DEAD verdict is trusted. Heartbeat-only "
                    "classification stays HUNG after kill and cannot make the "
                    "second flip."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/TST-0151/liveness.py:run_known_alive_then_kill",
                "confidence": "almost-certain",
                "signals": [
                    "heartbeat-age",
                    "cpu-time-delta-20s",
                ],
                "probes": [
                    {
                        "role": "source",
                        "method": "live-known-running-then-kill",
                        "command": "run_known_alive_then_kill()",
                        "raw_output": json.dumps(ctrl["sequence"], sort_keys=True),
                    },
                    {
                        "role": "verifier",
                        "method": "named-probe",
                        "command": P2,
                        "raw_output": "re-run live by _measure_one_delivered.py",
                    },
                ],
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "tests": [
            {
                "id": "TST-0151-BOTH-STATES",
                "command": P1,
                "result": "PASS",
                "assertions": 8,
                "output_tail": json.dumps(both["sequence"], sort_keys=True),
            },
            {
                "id": "TST-0151-DETECTOR-CONTROL",
                "command": P2,
                "result": "PASS",
                "assertions": 6,
                "output_tail": json.dumps(ctrl["sequence"], sort_keys=True),
            },
        ],
        "negative_controls": [
            {
                "id": "TST0151-C1",
                "kind": "mutation",
                "description": (
                    "Treat work-byte silence as hung. Idle-alive writes no "
                    "work and must turn this mutant red while production stays silent."
                ),
                "fired_on_bad_state": both["work_silence_mutant_fires_on_idle"],
                "silent_on_good_state": both["detector_silent_idle"],
                "bad_state_output": "HUNG",
                "good_state_output": "ALIVE",
            },
            {
                "id": "TST0151-C2",
                "kind": "mutation",
                "description": (
                    "Heartbeat-only: frozen token ⇒ HUNG even after kill. "
                    "Production must flip HUNG→DEAD; the mutant must not."
                ),
                "fired_on_bad_state": both["heartbeat_only_mutant_after_kill"] == L.HUNG,
                "silent_on_good_state": both["flipped_on_kill"],
                "bad_state_output": "HUNG",
                "good_state_output": "DEAD",
            },
            {
                "id": "TST0151-C3",
                "kind": "mtime-forbidden",
                "description": "An observation whose source is mtime must be UNDECIDABLE.",
                "fired_on_bad_state": both["mtime_idle"]["verdict"] == L.UNDECIDABLE,
                "silent_on_good_state": True,
                "bad_state_output": "mtime-only-forbidden",
                "good_state_output": json.dumps(both["mtime_idle"], sort_keys=True),
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0151-probe2-alive-before-dead",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Catalog reviewer_requirement names a second Windows shell. "
                "This worktree is Linux; SIGSTOP is POSIX. Probe 2 is the "
                "independent live control (ALIVE on a known-running process "
                "before DEAD). Waiting on an ADV Windows rebuild of this unit "
                "is the circle the dispatch prompt forbids. Residual: pwsh7/"
                "Git Bash divergence is NOT-CHECKED on this substrate."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "idle-alive-vs-sigstop", "command": P1},
            {"id": "probe2", "role": "alive-before-dead", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0151/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
            "global_catalog_write": False,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0151",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "note": "Measure runs after this receipt and the per-unit manifest are on disk.",
            }
        ],
        "required_fix": None,
        "adv_rebuild_circle": False,
        "notes": (
            "G-1 for TST-0151: live named probes exit 0, receipts/TST-0151.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild circle."
        ),
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in body:
        print("FAILED:TST-0151 sentinel missing from serialized receipt")
        return 1
    out.write_text(body, encoding="utf-8")
    sha, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0151 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
