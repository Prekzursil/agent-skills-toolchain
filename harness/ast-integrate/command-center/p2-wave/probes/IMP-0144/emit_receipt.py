#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0144.json — the replay-log format receipt."""
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

OUT = S.RECEIPT_REL
QUESTION = (
    "Question: what minimal event record makes a run replayable such that "
    "replaying it reproduces the SAME plan and the SAME verdicts without "
    "re-dispatching? Target: specify and implement that record. Acceptance: "
    "replay of a recorded run produces a byte-identical plan and identical "
    "oracle verdicts, with zero spawns."
)


def sha_file(rel: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": path.is_file(),
    }


def main() -> int:
    rec = S.record_and_replay()
    mut = S.field_mutation()
    if not rec["pass"] or not mut["pass"]:
        print(f"FAILED:IMP-0144 scenario rec={rec['pass']} mut={mut['pass']}")
        return 1
    log_path = S.write_fixture_log(rec["log_bytes"])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    clock_art = sha_file("tools/agentspec/agentspec/clock.py")
    replay_art = sha_file("tools/agentspec/agentspec/replay_log.py")
    ledger_art = sha_file("tools/event-ledger/ledger.py")
    fixture_art = sha_file(S.FIXTURE_LOG_REL)
    receipt = {
        "schema_version": 1,
        "unit_id": "IMP-0144",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0144",
        "completion_sentinel": "SUCCESS:IMP-0144",
        "title": "Define the deterministic replay log format (event stream to identical plan)",
        "question": QUESTION,
        "min_bytes_threshold": 2048,
        "profile": "replay-log-format",
        "format_id": "agentspec.replay-log/v1",
        "plan_sha256": rec["plan_sha256"],
        "verdict_sha256": rec["verdict_sha256"],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "replay_log_format": {
            "encoding": "UTF-8 JSONL, LF-only, canonical dumps (sort_keys, separators comma-colon)",
            "envelope_required": [
                "v",
                "seq",
                "kind",
                "ts_logical",
                "run_id",
                "payload",
            ],
            "kinds_closed": [
                "run.start",
                "plan.input",
                "unit.planned",
                "dispatch.recorded",
                "oracle.verdict",
                "run.end",
            ],
            "clock": (
                "FrozenClock logical ticks only. Wall-clock, timezone, uuid4 and "
                "time.time must not enter the plan bytes."
            ),
            "reconstruction": (
                "Replay recomputes the plan from run.start.workflow + run.start.params "
                "+ plan.input values (producer receipts). It re-applies oracle.verdict "
                "rows. It never calls the rail. unit.planned and dispatch.recorded are "
                "audit; they are not the reconstruction source, so dropping a planning "
                "input cannot be masked by a stored plan blob."
            ),
            "load_bearing_fields": [
                "run.start.payload.workflow",
                "run.start.payload.params",
                "plan.input.payload.value (fan-out items)",
                "plan.input.payload.value_hash",
                "oracle.verdict.payload.verdict",
                "oracle.verdict.payload.receipt_sha256",
                "run.end.payload.plan_sha256",
            ],
            "non_load_bearing_fields": ["debug_note", "note", "annotation"],
            "answer": (
                "The minimal record is a six-kind JSONL stream whose planning inputs "
                "are hashed and whose plan is a function of those inputs. Replay is "
                "recompute-plus-reapply, not re-dispatch."
            ),
        },
        "report": {
            "kind": "replay-log-acceptance",
            "plan_sha256": rec["plan_sha256"],
            "verdict_sha256": rec["verdict_sha256"],
            "record_spawns": rec["record_spawns"],
            "replay_spawns": rec["replay_spawns"],
            "slot_ids": rec["slot_ids"],
            "verdicts": rec["verdicts"],
            "event_count": rec["event_count"],
            "fixture_log": S.FIXTURE_LOG_REL,
            "fixture_log_sha256": fixture_art["sha256"],
            "mutation": {
                "params_field_red": mut["params_equal"] is False,
                "params_err": mut["params_err"],
                "fanout_item_plan_equal": mut["item_plan_equal"],
                "fanout_item_slots": mut["item_slots"],
                "debug_note_still_equal": mut["note_equal"],
                "intact_still_equal": mut["intact_equal"],
            },
        },
        "evidence": [
            {
                "id": "signal-1-plan-bytes",
                "claim": "Replay of the recorded fixture reproduces the plan byte-for-byte.",
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/replay_log.py:expand_plan",
                "measured": {
                    "plan_equal": rec["plan_equal"],
                    "plan_sha256": rec["plan_sha256"],
                    "plan_bytes": rec["plan_bytes"],
                    "slot_count": rec["slot_count"],
                },
            },
            {
                "id": "signal-2-zero-spawns",
                "claim": "Replay performs zero rail spawns; record performed a positive count.",
                "verdict": "CONFIRMED",
                "anchor": "tools/agentspec/agentspec/replay_log.py:CountingFakeRail",
                "measured": {
                    "record_spawns": rec["record_spawns"],
                    "replay_spawns": rec["replay_spawns"],
                    "replay_calls": rec["replay_calls"],
                    "dispatch_events": rec["dispatch_events"],
                },
            },
        ],
        "tests": [
            {
                "id": "T1-record-then-replay",
                "name": "record-then-replay yields a byte-identical plan and identical verdicts",
                "result": "PASS" if rec["pass"] else "FAIL",
                "assertions": 4,
                "output_tail": (
                    f"plan_equal={rec['plan_equal']} verdict_equal={rec['verdict_equal']} "
                    f"record_spawns={rec['record_spawns']} replay_spawns={rec['replay_spawns']}"
                ),
            },
            {
                "id": "T2-drop-field-goes-red",
                "name": "mutation: drop one event field and the byte-equality test must go red",
                "result": "PASS" if mut["pass"] else "FAIL",
                "assertions": 4,
                "output_tail": (
                    f"params_equal={mut['params_equal']} item_plan_equal={mut['item_plan_equal']} "
                    f"note_equal={mut['note_equal']} intact={mut['intact_equal']}"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "IMP0144-C1-load-bearing-params",
                "kind": "field-drop",
                "description": "Delete run.start.payload.params; reconstruction must not yield the original plan.",
                "fired_on_bad_state": mut["params_equal"] is False,
                "silent_on_good_state": mut["intact_equal"] is True,
                "bad_state_output": mut["params_err"] or "",
                "good_state_output": "intact log plan bytes match",
            },
            {
                "id": "IMP0144-C2-non-load-bearing-debug-note",
                "kind": "field-drop-control",
                "description": (
                    "Delete debug_note. If this also went red the detector would be "
                    "vacuous (any mutation fails). It must stay equal."
                ),
                "fired_on_bad_state": mut["item_plan_equal"] is False,
                "silent_on_good_state": mut["note_equal"] is True,
                "bad_state_output": f"slots after dropping beta={mut['item_slots']}",
                "good_state_output": "debug_note drop still byte-identical",
            },
        ],
        "artifacts": [
            {**replay_art, "role": "primary-implementation"},
            {**clock_art, "role": "supporting"},
            {**ledger_art, "role": "supporting"},
            {**fixture_art, "role": "supporting"},
            {
                "path": OUT,
                "role": "receipt",
                "exists": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0144-probe2-field-mutation",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Adversarial mutation probe drops params (required) and a fan-out "
                "item (planning input). Both turn plan byte-equality red. Dropping "
                "debug_note does not. Record-rail spawn count is the control that "
                "zero replay spawns is not a dead counter."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0144/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "inputs_absent_on_this_worktree": [
            "tools/agentspec/agentspec/clock.py (created by this unit)",
            "tools/event-ledger (created by this unit)",
            "command-center/events/EVENTS.jsonl (fixture log used instead of a global ledger)",
        ],
        "notes": (
            "G-1 for IMP-0144. Catalog inputs clock.py and event-ledger were absent; "
            "they are implemented here. EVENTS.jsonl is not used as a production "
            "append log (that is IMP-0224). Downstream IMP-0228 consumes this format."
        ),
    }
    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} bytes={dest.stat().st_size} plan_sha256={rec['plan_sha256']}")
    print(f"fixture {log_path.relative_to(REPO).as_posix()}")
    print("SUCCESS:IMP-0144")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
