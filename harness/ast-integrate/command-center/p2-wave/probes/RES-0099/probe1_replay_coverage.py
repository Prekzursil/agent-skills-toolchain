#!/usr/bin/env python3
"""Probe 1: replay real existing events through the proposed record; check field coverage.

Both-states: the live harvest (unlabelled gate-like JSON) must show ground_truth_class
as would-have-to-be-added; a synthetic complete record must show it as already-present.
Silent-in-both would mean the coverage detector is decorative.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

ART_REL = "command-center/research/RES-0099.json"
SENTINEL = (
    "SUCCESS:RES-0099 in the receipt AND a field-coverage report against "
    "real existing events plus a stated minimum-sample threshold"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0099-probe1 {msg}")
    return 1


def load_art() -> dict:
    path = REPO / ART_REL
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(fail("artifact missing"))
    return json.loads(path.read_text(encoding="utf-8"))


def field_by_name(cov: dict, name: str) -> dict:
    for row in cov["fields"]:
        if row["name"] == name:
            return row
    raise KeyError(name)


def main() -> int:
    art = load_art()
    text = json.dumps(art, ensure_ascii=True)
    if SENTINEL not in text:
        return fail("catalog sentinel absent from artifact")
    if art.get("unit_id") != "RES-0099":
        return fail(f"unit_id {art.get('unit_id')}")
    if str(art.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {art.get('state')}")

    art_cov = art.get("field_coverage") or {}
    frozen = [str(p).replace("\\", "/") for p in (art_cov.get("harvested_paths") or [])]
    if len(frozen) < 1:
        return fail("artifact harvested_paths empty; no real events to replay")
    records, missing = C.records_from_paths(frozen)
    if missing:
        return fail(f"frozen harvest paths missing: {missing[:5]}")
    live_cov = C.coverage_for_records(records)
    events_present = C.EVENTS_JSONL.is_file() and C.EVENTS_JSONL.stat().st_size > 0
    if int(art_cov.get("record_count") or -1) != int(live_cov["record_count"]):
        return fail(
            f"record_count artifact={art_cov.get('record_count')} replay={live_cov['record_count']}"
        )
    if live_cov["record_count"] < 1:
        return fail("zero real events replayed")
    if bool(art.get("events_jsonl", {}).get("present")) != bool(events_present):
        return fail("events_jsonl.present disagrees with disk")
    if events_present is False and art.get("replay_source") != "harvested-live-probe-json":
        return fail("EVENTS.jsonl absent but replay_source is not the harvest")
    if events_present:
        jsonl_rows = C.load_jsonl(C.EVENTS_JSONL)
        if int(art.get("events_jsonl", {}).get("line_records") or -1) != len(jsonl_rows):
            return fail("events_jsonl.line_records disagrees with disk")
        jart = art.get("events_jsonl_coverage") or {}
        mapped = []
        for rec in jsonl_rows:
            keys = C.collect_keys(rec)
            mapped.append(
                {
                    "path": C.EVENTS_REL,
                    "kind": "EVENTS.jsonl",
                    "keys": sorted(keys),
                    "predicted_derived": C.derive_predicted(rec)
                    if not rec.get("_parse_error")
                    else None,
                    "native_predicted": "predicted_class" in keys,
                    "native_truth": any(
                        k in keys
                        for k in ("ground_truth_class", "ground_truth", "y_true")
                    ),
                }
            )
        jlive = C.coverage_for_records(mapped)
        if int(jart.get("record_count") or -1) != int(jlive["record_count"]):
            return fail(
                f"jsonl record_count artifact={jart.get('record_count')} "
                f"replay={jlive['record_count']}"
            )
        if int(jlive["labelled_ground_truth_count"]) != 0:
            return fail("unexpected native ground truth on EVENTS.jsonl")
        if "labelled_ground_truth_count" not in jart:
            return fail("events_jsonl_coverage missing labelled_ground_truth_count")
        if int(jart["labelled_ground_truth_count"]) != 0:
            return fail("artifact overclaims labelled ground truth on EVENTS.jsonl")
        jgt = field_by_name(jlive, "ground_truth_class")
        if jgt["status"] not in {"would-have-to-be-added", "unmeasurable-no-events"}:
            return fail(f"EVENTS.jsonl ground_truth_class status {jgt['status']}")
    if int(live_cov["labelled_ground_truth_count"]) != 0:
        return fail("unexpected native ground truth on harvest; re-check mapper honesty")
    if "labelled_ground_truth_count" not in art_cov:
        return fail("artifact field_coverage missing labelled_ground_truth_count")
    if int(art_cov["labelled_ground_truth_count"]) != 0:
        return fail("artifact overclaims labelled ground truth")

    gt = field_by_name(live_cov, "ground_truth_class")
    if gt["status"] not in {"would-have-to-be-added", "unmeasurable-no-events"}:
        return fail(f"ground_truth_class live status {gt['status']}")
    pred = field_by_name(live_cov, "predicted_class")
    if pred["status"] not in {"proxy-only-must-add-first-class", "partial", "would-have-to-be-added"}:
        return fail(f"predicted_class should not be first-class on harvest, got {pred['status']}")

    # Both-states control: a complete synthetic record must flip ground_truth to already-present.
    complete_keys = set()
    for f in C.FIELDS:
        complete_keys.update(f["native"])
    complete = {
        "path": "synthetic/complete.json",
        "kind": "synthetic-complete",
        "keys": sorted(complete_keys),
        "predicted_derived": "POSITIVE",
        "native_predicted": True,
        "native_truth": True,
    }
    syn = C.coverage_for_records([complete])
    syn_gt = field_by_name(syn, "ground_truth_class")
    if syn_gt["status"] != "already-present":
        return fail(f"complete-record control did not go green: {syn_gt['status']}")
    empty = C.coverage_for_records(
        [
            {
                "path": "synthetic/empty.json",
                "kind": "synthetic-empty",
                "keys": ["unrelated"],
                "predicted_derived": None,
                "native_predicted": False,
                "native_truth": False,
            }
        ]
    )
    empty_gt = field_by_name(empty, "ground_truth_class")
    if empty_gt["status"] != "would-have-to-be-added":
        return fail(f"empty-record control silent: {empty_gt['status']}")
    if syn_gt["status"] == empty_gt["status"]:
        return fail("coverage detector silent in both states")

    if live_cov["rate_may_be_quoted"] is not False:
        return fail("must not quote a rate from unlabelled harvest")
    if art.get("rate_quote", {}).get("status") not in {"RATE-NOT-QUOTED", "NOT-QUOTED"}:
        return fail(f"artifact quoted a rate it cannot: {art.get('rate_quote')}")

    added = set(art_cov.get("fields_that_would_have_to_be_added") or [])
    if "ground_truth_class" not in added:
        return fail("ground_truth_class missing from would-have-to-be-added")
    if "gate_id" not in added:
        return fail("gate_id missing from would-have-to-be-added")
    live_added = {f["name"] for f in live_cov["fields"] if f["status"] != "already-present"}
    if live_added != added:
        return fail(
            f"added-field set drifted frozen={sorted(added)} replay={sorted(live_added)}"
        )

    print(
        json.dumps(
            {
                "probe": "probe1_replay_coverage",
                "replay_source": art.get("replay_source"),
                "record_count": live_cov["record_count"],
                "labelled": live_cov["labelled_ground_truth_count"],
                "events_jsonl_present": events_present,
                "ground_truth_status": gt["status"],
                "predicted_status": pred["status"],
                "complete_control": syn_gt["status"],
                "empty_control": empty_gt["status"],
                "rate_may_be_quoted": live_cov["rate_may_be_quoted"],
            },
            sort_keys=True,
        )
    )
    print(
        f"replay_n={live_cov['record_count']} labelled=0 "
        f"gt={gt['status']} complete_control={syn_gt['status']}"
    )
    print("SUCCESS:RES-0099-probe1 replayed real events; field coverage recomputed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
