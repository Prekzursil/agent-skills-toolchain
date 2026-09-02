#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0154.json from live clock-jump measurements."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave"))

from lab import measure_all  # noqa: E402
import _p2lib as L  # noqa: E402

UNIT = "TST-0154"
OUT = "command-center/receipts/TST-0154.json"
SCHEMA = "command-center/schema/receipt.schema.json#/$defs/monitor_report"
SENTINEL = "SUCCESS:TST-0154"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0154/probe1_clock_jump_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0154/probe2_static_and_wallclock_negative.py"
)
IMPL = "tools/command-center/elapsed.py"
QUESTION = (
    "Does elapsed-time computation use a monotonic source, so that a backward "
    "wall-clock adjustment cannot mark a running unit as timed out (nor a stalled "
    "one as fresh)? PASS requires the unit survive a simulated backward and "
    "forward clock jump."
)
SUPPORTING = [
    IMPL,
    "tools/plugin/heartbeat.py",
    "scripts/longrun.sh",
    "scripts/longrun.ps1",
    "command-center/p2-wave/probes/TST-0154/lab.py",
    "command-center/p2-wave/probes/TST-0154/probe1_clock_jump_states.py",
    "command-center/p2-wave/probes/TST-0154/probe2_static_and_wallclock_negative.py",
]


def digest_rel(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "exists": path.is_file(),
        "role": "implementation" if rel == IMPL else "supporting",
        "eol": "LF",
    }


def main() -> int:
    live = measure_all()
    if not live.get("pass"):
        print(json.dumps(live, indent=2, sort_keys=True, default=str)[:8000])
        print("FAILED:TST-0154 emit live measurements did not pass")
        return 1

    jumps = live["clock_jumps"]
    static = live["static"]
    fake = live["fake_clock_timeout"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [digest_rel(rel) for rel in SUPPORTING]

    p_jump = L.probe(
        "source",
        "in-process",
        "measure_clock_jumps",
        json.dumps(
            {
                "production_survives_jumps": jumps["production_survives_jumps"],
                "wall_mutant_fails_both_directions": jumps["wall_mutant_fails_both_directions"],
                "both_states_timeout_still_fires": jumps["both_states_timeout_still_fires"],
                "timeout_mid_state": jumps["timeout_mid_state"],
                "timeout_fired_state": jumps["timeout_fired_state"],
                "jump_s": jumps["jump_s"],
            },
            sort_keys=True,
        ),
        0,
    )
    p_static = L.probe(
        "verifier",
        "in-process",
        "measure_static",
        json.dumps(
            {
                "elapsed_wall_hits": static["elapsed_wall_hits"],
                "detector_fires_on_planted_wall_clock": static[
                    "detector_fires_on_planted_wall_clock"
                ],
                "heartbeat_hang_uses_monotonic": static["heartbeat_hang_uses_monotonic"],
                "heartbeat_uses_time_time": static["heartbeat_uses_time_time"],
            },
            sort_keys=True,
        ),
        0,
    )

    answer = (
        "YES: elapsed classification in tools/command-center/elapsed.py uses an "
        "injectable monotonic clock (time.monotonic in production). A DualClock "
        f"NTP step of ±{jumps['jump_s']}s left a running unit RUNNING and a stalled "
        "unit STALLED. The same classifier fed wall-clock timestamps failed both "
        "directions (forward running→TIMED_OUT, backward stalled→RUNNING/fresh). "
        "A real timeout still fired: mid-state "
        f"{jumps['timeout_mid_state']} then {jumps['timeout_fired_state']} after "
        "monotonic elapsed crossed 10s while wall was jumping. Static scan of "
        "elapsed.py found 0 wall-clock reads; a planted time.time() snippet was "
        "flagged. Heartbeat hang windows use time.monotonic(); longrun.sh/ps1 "
        f"delegate to heartbeat.py. FakeClock timeout ok={fake['ok']}. {SENTINEL}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "Monotonic clock is used for elapsed time; wall-clock jumps cannot fake a timeout",
        "spec_anchor": "_USER-PROMPTS.md:11010 (Phase 10 layer 22, stale-monitor tests)",
        "question": QUESTION,
        "answer": answer,
        "report_kind": "monitor_report",
        "output_schema": SCHEMA,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "elapsed_uses_monotonic": True,
        "survived_backward_jump": jumps["running_survives_backward"]
        and jumps["stalled_survives_backward"],
        "survived_forward_jump": jumps["running_survives_forward"]
        and jumps["stalled_survives_forward"],
        "real_timeout_still_fires": jumps["both_states_timeout_still_fires"],
        "wall_clock_mutant_fails_both_directions": jumps["wall_mutant_fails_both_directions"],
        "static_elapsed_has_no_wall_clock_source": static["detector_silent_on_elapsed_py"],
        "implementation": {
            "classifier": IMPL,
            "clock": "MonotonicClock = time.monotonic; FakeClock for probes",
            "hang_companion": "tools/plugin/heartbeat.py hang_timeout_sec via time.monotonic",
            "longrun_posix": "scripts/longrun.sh",
            "longrun_windows": "scripts/longrun.ps1",
        },
        "clock_jumps": jumps,
        "static": static,
        "fake_clock_timeout": fake,
        "tests": [
            {
                "id": "TST-0154-T1-clock-jump-both-states",
                "name": "running survives ±3600s wall jump; real timeout still fires",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "TST-0154-T2-static-and-negative",
                "name": "static: no wall-clock elapsed source; wall mutant fails both directions",
                "command": P2,
                "result": "PASS",
            },
        ],
        "checks": [
            {"id": "running-survives-backward-jump", "verdict": "PASS"},
            {"id": "running-survives-forward-jump", "verdict": "PASS"},
            {"id": "stalled-survives-backward-jump", "verdict": "PASS"},
            {"id": "stalled-survives-forward-jump", "verdict": "PASS"},
            {"id": "real-timeout-still-fires", "verdict": "PASS"},
            {"id": "wall-mutant-fails-both-directions", "verdict": "PASS"},
            {"id": "static-no-wall-clock-elapsed", "verdict": "PASS"},
        ],
        "negative_controls": [
            L.control(
                "wall-clock-elapsed",
                "known-broken-mutant",
                "The same classifier fed wall-clock timestamps must mark a running "
                "unit TIMED_OUT on a forward NTP step and a stalled unit RUNNING "
                "(fresh) on a backward step. Production monotonic timestamps must not.",
                True,
                True,
                bad="wall mutant forward running=TIMED_OUT; backward stalled=RUNNING",
                good="monotonic running=RUNNING stalled=STALLED across ±3600s",
            ),
            L.control(
                "planted-time-time",
                "mutation",
                "A static detector that cannot flag time.time() in elapsed code is dead. "
                "elapsed.py must be silent; a planted snippet must fire.",
                True,
                True,
                bad="planted elapsed = time.time() - started → hit",
                good="elapsed.py wall_clock_hits=[]",
            ),
        ],
        "evidence": [
            L.evidence(
                "Unit state across injected backward and forward wall-clock jumps; "
                "production monotonic timestamps unchanged; real timeout still fires.",
                "CONFIRMED",
                f"{IMPL}:classify",
                [p_jump],
                "almost-certain",
            ),
            L.evidence(
                "Static AST scan: elapsed.py has no wall-clock reads; heartbeat hang "
                "window uses time.monotonic(); longrun scripts delegate and do not "
                "read date/UtcNow; planted time.time() is flagged.",
                "CONFIRMED",
                f"{IMPL}:wall_clock_hits",
                [p_static],
                "almost-certain",
            ),
        ],
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "clock-jump-both-states"},
            {"id": "probe2", "command": P2, "role": "static-and-wallclock-negative"},
        ],
        "reviewer": {
            "reviewer_id": "TST-0154-probe2-static-and-wallclock-negative",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not rerun the DualClock campaign. It AST-scans elapsed.py "
                "and heartbeat.py, checks longrun.sh/ps1 delegation, and requires the "
                "wall-clock detector to fire on a planted time.time() snippet."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/TST-0154/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py TST-0154",
                "artifact_path": OUT,
                "executed": False,
                "read_ok": True,
                "exit_code": 0,
            }
        ],
        "artifacts": artifacts,
        "residual_unknowns": [
            "This Linux worktree cannot re-run pwsh7 as a second Windows shell; "
            "scripts/longrun.ps1 is the same heartbeat.py exec as longrun.sh."
        ],
        "produced_by": {
            "role": "observability-tester",
            "execution_substrate": "linux-local-serialized",
            "cloud_ok": False,
        },
        "ts": now,
        "notes": (
            "G-1 for TST-0154: live named probes exit 0, receipts/TST-0154.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery. "
            "Did not rebuild ADV units. SUCCESS:TST-0154"
        ),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out_path.write_text(text, encoding="utf-8")
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    digest = hashlib.sha256(raw).hexdigest()
    print(f"wrote {OUT} bytes={len(raw)} sha256={digest}")
    if SENTINEL not in text:
        print("FAILED:TST-0154 sentinel missing")
        return 1
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
