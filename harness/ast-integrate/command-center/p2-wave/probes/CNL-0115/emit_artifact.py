#!/usr/bin/env python3
"""Emit the CNL-0115 catalog artifact (JSON bytes at the .md output_path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    ACK_UNCHANGED,
    SLEEP,
    WAKE_DELTA,
    WAKE_NEW,
    WAKE_REOPEN,
    classify,
    instantiate,
    nearest_sibling,
    record_decision,
)
from fixtures import (  # noqa: E402
    MATERIAL_V2,
    QUESTION,
    task_clock,
    task_delta,
    task_new,
    task_reask,
    task_reopen,
    task_stale_six_weeks,
)
from preset import PRESET  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0115-standing-watch-council-long-running-trigger-woken-low-inte.md"
)
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0115/council-preset.schema.json"
)
QUESTION_TEXT = (
    "A standing council is mostly asleep - what wakes it, what state does it "
    "carry between wakings, and how does it avoid re-litigating a question it "
    "already settled six weeks ago?"
)
EXPECTED_SIBLING = "C-cited:P51-timeboxed-spike-council"


def load_siblings() -> list[dict]:
    return json.loads((HERE / "siblings.json").read_text(encoding="utf-8"))["presets"]


def main() -> int:
    siblings = load_siblings()
    stale = task_stale_six_weeks()
    clock = task_clock()
    delta = task_delta()
    new_q = task_new()
    reopen = task_reopen()
    reask = task_reask()

    inst_stale = instantiate(PRESET, stale)
    inst_clock = instantiate(PRESET, clock)
    inst_delta = instantiate(PRESET, delta)
    inst_new = instantiate(PRESET, new_q)
    inst_reopen = instantiate(PRESET, reopen)
    inst_reask = instantiate(PRESET, reask)

    sib = nearest_sibling(PRESET, siblings)
    if sib["id"] != EXPECTED_SIBLING:
        print(f"FAILED:emit nearest sibling {sib['id']} != {EXPECTED_SIBLING}")
        print(json.dumps(sib["ranked"], indent=2))
        return 1
    if sib["distance"] <= 0:
        print("FAILED:emit name-only duplicate of sibling")
        return 1
    required_diffs = {"trigger_woken", "sleep_default", "settled_ledger"}
    got = {d["field"] for d in sib["measurable_diffs"]}
    missing = required_diffs - got
    if missing:
        print(f"FAILED:emit sibling differential missing {sorted(missing)}")
        return 1

    cases = {
        "stale_six_weeks": classify(event=stale["event"], ledger=stale["ledger"]),
        "clock_tick": classify(event=clock["event"], ledger=clock["ledger"]),
        "material_delta": classify(event=delta["event"], ledger=delta["ledger"]),
        "new_question": classify(event=new_q["event"], ledger=new_q["ledger"]),
        "authorized_reopen": classify(event=reopen["event"], ledger=reopen["ledger"]),
        "bare_reask": classify(event=reask["event"], ledger=reask["ledger"]),
    }
    if cases["stale_six_weeks"]["disposition"] != ACK_UNCHANGED:
        print("FAILED:emit six-week stale re-litigated")
        return 1
    if cases["stale_six_weeks"]["wake"] or cases["stale_six_weeks"]["new_decision_id"]:
        print("FAILED:emit stale produced a new decision")
        return 1
    if cases["clock_tick"]["disposition"] != SLEEP:
        print("FAILED:emit clock tick woke the council")
        return 1
    if cases["material_delta"]["disposition"] != WAKE_DELTA:
        print("FAILED:emit material delta did not wake")
        return 1
    if cases["new_question"]["disposition"] != WAKE_NEW:
        print("FAILED:emit new question did not wake")
        return 1
    if cases["authorized_reopen"]["disposition"] != WAKE_REOPEN:
        print("FAILED:emit authorized reopen did not wake")
        return 1
    if cases["bare_reask"]["wake"]:
        print("FAILED:emit bare re-ask woke")
        return 1

    if inst_stale["phase"] != "sleep" or inst_delta["phase"] != "wake":
        print("FAILED:emit sleep/wake phases inverted")
        return 1
    if inst_stale["voting_seats"]:
        print("FAILED:emit voting seats seated while asleep")
        return 1
    if inst_delta["voting_seats"] != ["Chair", "Skeptic", "Pragmatist"]:
        print(f"FAILED:emit wake roster {inst_delta['voting_seats']}")
        return 1
    if inst_stale["protocol_schedule"] == inst_delta["protocol_schedule"]:
        print("FAILED:emit sleep and wake schedules identical")
        return 1

    after_delta = record_decision(
        delta["ledger"],
        question_id=QUESTION,
        material_inputs=MATERIAL_V2,
        decision_id="D-2026-08-24-shipping-window",
        lineage_root=(
            "idea:I-saturday-window→option:O-policy-v2→claim:C-measured-load→"
            "vote:V-2-1→decision:D-2026-08-24-shipping-window"
        ),
    )
    live_ids = [r["question_id"] for r in after_delta["settled"]]
    if live_ids.count(QUESTION) != 1:
        print("FAILED:emit forked a second live decision for the same question")
        return 1

    doc = {
        "unit_id": "CNL-0115",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0115",
        "completion_sentinel": "SUCCESS:CNL-0115",
        **PRESET,
        "nearest_sibling": {
            "id": sib["id"],
            "source": sib["source"],
            "named_explicitly": True,
            "distance": sib["distance"],
            "ranked": sib["ranked"],
            "measurable_diffs": sib["measurable_diffs"],
            "library_file_on_this_worktree": False,
            "library_path_catalogued": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
            ),
            "reconstruction_basis": (
                "WORK-UNIT-CATALOG.json CNL-0045 names P51 timeboxed-spike-council "
                "(low-intensity, max_rounds=2, majority). This unit does not claim "
                "a byte copy of the absent 72-preset library."
            ),
        },
        "question": QUESTION_TEXT,
        "answers": {
            "what_wakes_it": (
                "A named trigger predicate bound by DutySentinel before sleep: "
                "content-hash change on a watched source, a threshold breach, or "
                "an authorized reopen (reopen_token AND new_evidence_pointer). "
                "A clock tick is not a trigger. Cosmetic fields (etag, ad markup, "
                "wall-clock, asker_id) cannot wake. watch.trigger_woken and "
                "watch.clock_tick_is_not_a_trigger are locked dials."
            ),
            "what_state_it_carries_between_wakings": (
                "sleep_state = {watch_id, settled[], bindings[], replay_seeds={}}. "
                "settled[] is the CNL-0075 lineage-bearing decision ledger, one "
                "live row per question_id. bindings[] are the DutySentinel trigger "
                "predicates. replay_seeds stay empty while asleep: this is not a "
                "CNL-0011 paused-transcript freeze. Full transcripts, wall-clock, "
                "and participant mood are archived off the live state."
            ),
            "how_it_avoids_relitigating_six_weeks_later": (
                "question_fingerprint = sha256(question_id + canonical "
                "material_inputs). Wall-clock, elapsed_days, etag, and ad_markup "
                "are dropped before the hash. A trigger whose fingerprint matches "
                "a settled row returns ACK-UNCHANGED, seats no voting roles, and "
                "writes no new decision_id. The six-week re-ask is that case. A "
                "material-input digest change wakes with the prior decision as "
                "exhibit (not a blank slate). A bare re-ask without token+evidence "
                "does not reopen."
            ),
        },
        "instantiations": {
            "stale_six_weeks": inst_stale,
            "clock_tick": inst_clock,
            "material_delta": inst_delta,
            "new_question": inst_new,
            "authorized_reopen": inst_reopen,
            "bare_reask": inst_reask,
        },
        "classify_cases": cases,
        "negative_control": {
            "rejected_state": (
                "same question_id and material inputs, elapsed_days=42, "
                "council seats the panel and records a new competing decision"
            ),
            "check_does": (
                "classify returns disposition=ACK-UNCHANGED, wake=false, "
                "new_decision_id=null; instantiate seats WatchClerk+Archivist+"
                "DutySentinel only; voting_seats is empty"
            ),
            "observed_disposition": cases["stale_six_weeks"]["disposition"],
            "observed_wake": cases["stale_six_weeks"]["wake"],
            "observed_new_decision_id": cases["stale_six_weeks"]["new_decision_id"],
            "observed_voting_seats": inst_stale["voting_seats"],
        },
        "library_disclosure": {
            "12_COUNCIL_PROTOCOLS_AND_PRESETS_json": False,
            "11_COUNCIL_SPECIFICATION_schema_json": False,
            "honest_limit": (
                "Nearest sibling is named from catalog-cited P51, not from a "
                "live parse of the 72-record library. If that file lands, re-run "
                "nearest_sibling over its presets; a closer C-id replaces "
                "C-cited:P51-timeboxed-spike-council."
            ),
        },
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver "
            "tries the network. This unit validates against the per-unit schema "
            f"{LOCAL_SCHEMA}. Overwriting the shared catalog schema would be a "
            "sibling rebuild circle."
        ),
        "tests": [
            {
                "id": "instantiate-stale-sleep",
                "result": "PASS",
                "roster": [s["role_id"] for s in inst_stale["roster"]],
                "schedule": [s["id"] for s in inst_stale["protocol_schedule"]],
                "voting": inst_stale["voting"].get("rule"),
                "stopping": inst_stale["stopping"].get("expression"),
            },
            {
                "id": "instantiate-delta-wake-differs",
                "result": "PASS",
                "roster": inst_delta["voting_seats"],
                "schedule": [s["id"] for s in inst_delta["protocol_schedule"]],
            },
            {
                "id": "nearest-sibling-P51",
                "result": "PASS",
                "sibling": sib["id"],
                "distance": sib["distance"],
            },
        ],
    }
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    wrap_errs = list(Draft202012Validator(schema).iter_errors(doc))
    if wrap_errs:
        print("FAILED:emit live schema errors")
        for e in wrap_errs[:8]:
            print(f"  {e.json_path}: {e.message}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT} bytes={len(text.encode('utf-8'))}")
    print(f"nearest_sibling={sib['id']} distance={sib['distance']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
