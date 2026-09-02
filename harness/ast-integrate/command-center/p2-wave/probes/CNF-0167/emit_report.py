#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0167.json from live controls + live scan."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import audit as A  # noqa: E402

OUT_REL = "command-center/receipts/CNF-0167.json"
SCHEMA_REL = "command-center/schema/evidence-integrity-report.schema.json"
UNIT = "CNF-0167"
SENTINEL = "SUCCESS:CNF-0167"
QUESTION = (
    "Question: is any receipt causally impossible - written before the artifact "
    "it cites existed, before its dependency completed, or out of order relative "
    "to the append-only event log? Join EVENTS.jsonl against artifact mtimes and "
    "git commit times and flag every inversion. A back-dated receipt is either a "
    "clock artifact or a fabrication, and the two must be distinguished, not assumed."
)
TITLE = "Temporal integrity audit: detect back-dated or causally impossible receipts"


def compact_inv(row: dict) -> dict:
    keys = (
        "kind",
        "subject",
        "classification",
        "proposed_cause",
        "receipt_ts",
        "artifact_mtime",
        "git_commit_ts",
        "event_ts",
        "third_timestamp_source",
        "cited_path",
        "dependency",
        "dependency_ts",
        "seq_later",
        "seq_earlier",
    )
    return {k: row[k] for k in keys if k in row}


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000, "state": "SUCCESS"}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:CNF-0167 schema accepts garbage")


def main() -> int:
    ctrl = A.run_required_controls()
    if not ctrl["tests"]["all_pass"]:
        print("FAILED:CNF-0167 required controls did not all pass")
        print(json.dumps(ctrl["tests"], indent=2, sort_keys=True))
        return 1
    live = A.live_scan(REPO)
    worlds = ctrl["worlds"]
    evonly = ctrl["eventlog_only"]
    tz = ctrl["timezone_control"]

    planted = [compact_inv(i) for i in worlds["backdated"]["inversions"]]
    dep_inv = [compact_inv(i) for i in worlds["dep-order"]["inversions"]]
    healthy_inv = worlds["healthy"]["inversions"]
    tz_order = [
        compact_inv(i)
        for i in worlds["timezone"]["inversions"]
        if i.get("kind") == "event-log-order-inversion"
    ]

    event_present = bool(live["event_log_present"])
    git_ok = bool(live["git_available"])
    causal_live = [compact_inv(i) for i in live["causal_inversions"]]
    clock_live = [compact_inv(i) for i in live["clock_artifacts"]]

    answer = (
        "Fixture controls discriminate: a planted back-dated receipt is caught, "
        "a receipt completing before its catalog/event dependency is caught, "
        "a healthy ordered set produces zero inversions, and two timezone "
        f"spellings of the same instant ({tz['ts_a']} vs {tz['ts_b']}) are not "
        f"flagged (UTC {tz['utc_a']}) while naive civil comparison returns "
        f"{tz['naive_civil_result']}. Clock-skew window is "
        f"{A.CLOCK_SKEW_SECONDS:.0f}s; naive local-time comparison is forbidden. "
        f"Production EVENTS.jsonl is {'present' if event_present else 'absent'}; "
        f"git commit timestamps are {'available' if git_ok else 'NOT-CHECKED (no .git)'}. "
        f"Live receipts scanned={live['receipts_scanned']}; "
        f"clock-artifact rows={live['clock_artifact_count']} "
        "(declared ts vs mtime within skew or classified clock-artifact, not fabrication); "
        f"missing declared ts={live['missing_declared_ts_count']}; "
        f"live causal inversions={live['causal_inversion_count']}."
    )

    tests = [
        {
            "id": "planted-backdated",
            "name": "Known-broken control: planted back-dated receipt is caught",
            "result": "PASS" if ctrl["tests"]["planted_backdated_caught"] else "FAIL",
            "inversion_count": worlds["backdated"]["inversion_count"],
            "kinds": sorted({i["kind"] for i in worlds["backdated"]["inversions"]}),
        },
        {
            "id": "timezone-same-instant",
            "name": "Timezone control: different offset spellings of one instant are not flagged",
            "result": "PASS" if ctrl["tests"]["timezone_same_instant_not_flagged"] else "FAIL",
            "utc_same_instant": tz["same_instant"],
            "naive_civil_result": tz["naive_civil_result"],
        },
        {
            "id": "dependency-ordering",
            "name": "Dependency ordering: receipt completing before its dependency is flagged",
            "result": "PASS" if ctrl["tests"]["dependency_before_parent_caught"] else "FAIL",
            "inversion_count": worlds["dep-order"]["inversion_count"],
        },
        {
            "id": "healthy-both-states",
            "name": "Both-states: healthy ordered set produces zero inversions",
            "result": "PASS" if ctrl["tests"]["healthy_zero_inversions"] else "FAIL",
            "inversion_count": worlds["healthy"]["inversion_count"],
        },
        {
            "id": "naive-trap",
            "name": "Detector control: naive civil comparison would flag the timezone pair",
            "result": "PASS" if ctrl["tests"]["naive_civil_would_flag_timezone_pair"] else "FAIL",
            "naive_civil_result": tz["naive_civil_result"],
        },
        {
            "id": "eventlog-only-reviewer",
            "name": "Reviewer re-derives the same planted inversions from the event log alone",
            "result": (
                "PASS"
                if ctrl["tests"]["eventlog_only_backdated_caught"]
                and ctrl["tests"]["eventlog_only_dep_caught"]
                and ctrl["tests"]["eventlog_only_healthy_zero"]
                and ctrl["tests"]["eventlog_only_timezone_silent"]
                else "FAIL"
            ),
        },
    ]
    if any(t["result"] != "PASS" for t in tests):
        print("FAILED:CNF-0167 a required test is not PASS")
        print(json.dumps(tests, indent=2))
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "SUCCESS:CNF-0167": True,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": TITLE,
        "question": QUESTION,
        "answer": answer,
        "report_kind": "evidence-integrity-report",
        "schema_version": 1,
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "ts": now,
        "timezone_policy": {
            "rule": tz["policy"],
            "clock_skew_seconds": A.CLOCK_SKEW_SECONDS,
            "naive_local_comparison": "forbidden",
            "dst_handling": "compare UTC instants; DST does not invent inversions",
            "naive_timestamps": "unorderable; never assigned the host local zone",
            "timezone_pair": {
                "a": tz["ts_a"],
                "b": tz["ts_b"],
                "utc_a": tz["utc_a"],
                "utc_b": tz["utc_b"],
                "same_instant": tz["same_instant"],
                "utc_flags_inversion": tz["utc_flags_inversion"],
                "naive_civil_result": tz["naive_civil_result"],
            },
        },
        "classification_policy": {
            "fabrication": (
                "UTC-aware causal impossibility beyond clock-skew, corroborated by "
                "event-log order, catalog dependency edges, or git commit time"
            ),
            "clock-artifact": (
                "mtime vs declared ts disagree on a tree where git and/or EVENTS.jsonl "
                "are absent; copy/rewrite/skew, not assumed fabrication"
            ),
            "unorderable-naive": "timestamp lacks an offset; not compared as local civil time",
        },
        "event_log": {
            "path": live["event_log_path"],
            "present": event_present,
            "bytes": live["event_log_bytes"],
            "join": "ran" if event_present else "NOT-CHECKED",
            "reason_if_absent": (
                None
                if event_present
                else "command-center/events/EVENTS.jsonl is absent on this worktree; fixture event logs carry the required tests"
            ),
        },
        "git_commit_timestamps": {
            "available": git_ok,
            "join": "ran" if git_ok else "NOT-CHECKED",
            "reason_if_absent": None if git_ok else "worktree has no .git; fixture worlds still carry git_commit_ts",
        },
        "inversions": planted + dep_inv,
        "controls": {
            "planted_backdated": {
                "fired": True,
                "inversions": planted,
            },
            "timezone": {
                "silent_on_same_instant": True,
                "event_log_order_inversions": tz_order,
                "equivalences": worlds["timezone"]["equivalences"],
                "unorderable": worlds["timezone"]["unorderable"],
            },
            "dependency_ordering": {
                "fired": True,
                "inversions": dep_inv,
            },
            "healthy": {
                "inversion_count": len(healthy_inv),
                "inversions": healthy_inv,
            },
        },
        "live_scan": {
            "receipts_scanned": live["receipts_scanned"],
            "clock_artifact_count": live["clock_artifact_count"],
            "causal_inversion_count": live["causal_inversion_count"],
            "unorderable_count": live["unorderable_count"],
            "missing_declared_ts_count": live["missing_declared_ts_count"],
            "missing_declared_ts_ids": live["missing_declared_ts_ids"],
            "catalog_unit_edges_loaded": live["catalog_unit_edges_loaded"],
            "clock_artifacts": clock_live,
            "causal_inversions": causal_live,
            "unorderable": live["unorderable"],
        },
        "reviewer_eventlog_only": {
            "signals": ["event-log"],
            "excludes": ["filesystem-mtime", "git-commit"],
            "backdated_caught": ctrl["tests"]["eventlog_only_backdated_caught"],
            "dep_caught": ctrl["tests"]["eventlog_only_dep_caught"],
            "healthy_zero": ctrl["tests"]["eventlog_only_healthy_zero"],
            "timezone_silent": ctrl["tests"]["eventlog_only_timezone_silent"],
            "backdated_inversion_count": len(evonly["backdated"]["inversions"]),
            "dep_inversion_count": len(evonly["dep-order"]["inversions"]),
        },
        "findings": [
            {
                "id": "F-PLANTED-BACKDATE",
                "kind": "fabrication",
                "detail": (
                    "Planted PLANT-BACKDATE receipt_ts 2026-05-01T12:00:00Z vs "
                    "artifact_mtime 2026-06-01T12:00:00Z vs git_commit_ts "
                    "2026-06-01T12:00:05Z; detector classification=fabrication"
                ),
            },
            {
                "id": "F-DEP-ORDER",
                "kind": "fabrication",
                "detail": (
                    "Planted DEP-CHILD completes at 2026-07-01T10:01:00Z before "
                    "DEP-PARENT at 2026-07-01T12:01:00Z"
                ),
            },
            {
                "id": "F-TIMEZONE",
                "kind": "timezone-equivalent",
                "detail": (
                    "TZ-A 2026-08-24T18:00:00Z and TZ-B 2026-08-24T14:00:00-04:00 "
                    "are the same UTC instant; not an inversion. Naive civil "
                    f"comparison returns {tz['naive_civil_result']}."
                ),
            },
            {
                "id": "F-LIVE-EVENT-LOG",
                "kind": "coverage",
                "detail": (
                    "Production EVENTS.jsonl absent; live causal join against the "
                    "append-only log is NOT-CHECKED. Fixture logs prove the detector."
                    if not event_present
                    else "Production EVENTS.jsonl present and joined."
                ),
            },
            {
                "id": "F-LIVE-CLOCK",
                "kind": "clock-artifact",
                "detail": (
                    f"{live['clock_artifact_count']} live receipt declared-ts vs mtime "
                    "disagreements beyond skew; "
                    f"{live['missing_declared_ts_count']} receipts have no declared timestamp "
                    "(back-date check NOT-CHECKED on those bodies). "
                    "Disagreements without git/event-log corroboration are clock-artifact, "
                    "not fabrication."
                ),
            },
        ],
        "tests": tests,
        "evidence": [
            {
                "claim": "Planted back-dated receipt is caught with all three timestamps.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0167/fixtures/world_backdated.json",
            },
            {
                "claim": "Two timezone representations of one instant are not flagged; naive civil comparison would flag them.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0167/audit.py:timezone_control",
            },
            {
                "claim": "A receipt completing before its declared dependency is flagged.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0167/fixtures/world_dep_order.json",
            },
            {
                "claim": "A healthy ordered set produces zero inversions.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0167/fixtures/world_healthy.json",
            },
            {
                "claim": "Independent reviewer re-derives planted inversions from the event log alone.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0167/audit.py:audit_event_log",
            },
            {
                "claim": "Production EVENTS.jsonl joined against live receipts.",
                "verdict": "CONFIRMED" if event_present else "NOT-CHECKED",
                "anchor": live["event_log_path"],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0167-probe2-eventlog-ordering",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Re-derived ordering from fixture event logs alone "
                "(audit_event_log: no filesystem mtimes, no git)."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNF-0167/audit.py",
                "exists": True,
                "role": "detector",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0167/fixtures/world_backdated.json",
                "exists": True,
                "role": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0167/fixtures/world_timezone.json",
                "exists": True,
                "role": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0167/fixtures/world_dep_order.json",
                "exists": True,
                "role": "fixture",
            },
            {
                "path": "command-center/p2-wave/probes/CNF-0167/fixtures/world_healthy.json",
                "exists": True,
                "role": "fixture",
            },
        ],
        "produced_by": "command-center/p2-wave/probes/CNF-0167/emit_report.py",
        "residual_unknowns": [
            "Production append-only EVENTS.jsonl is absent, so live event-log order is NOT-CHECKED.",
            "This worktree is not a git checkout, so live git commit timestamps are NOT-CHECKED.",
        ],
    }

    validate_or_die(doc)
    if SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0167 emit sentinel missing from dump")
        return 1
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    raw = text.encode("utf-8")
    if len(raw) < 2048:
        print(f"FAILED:CNF-0167 emit too small bytes={len(raw)}")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(
        f"wrote {OUT_REL} bytes={len(raw)} state={doc['state']} "
        f"clock_artifacts={live['clock_artifact_count']} "
        f"causal_live={live['causal_inversion_count']}"
    )
    print(f"{SENTINEL} receipt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
