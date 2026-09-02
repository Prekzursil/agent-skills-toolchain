#!/usr/bin/env python3
"""Probe 1: lineage record schema and supersession links.

Both-states on the overturn path: commit_overturn(mark=True) writes
superseded_by on the older row and the contradiction scan stays silent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixture import NEWER, OLDER, QUESTION, seeded_log  # noqa: E402
from tools.council.outcomes.lineage_export import (  # noqa: E402
    STATUS_LIVE,
    STATUS_SUPERSEDED,
    LineageSchemaError,
    append_binding,
    build_record,
    commit_overturn,
    empty_log,
    save_log,
    scan_live_contradictions,
    validate_record,
)

REQUIRED = (
    "decision_id",
    "council_id",
    "question",
    "question_key",
    "verdict",
    "inputs",
    "deciding_rule",
    "tally",
    "dissents",
    "supersedes",
    "superseded_by",
    "status",
    "recorded_at",
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0351-probe1 {msg}")
    return 1


def main() -> int:
    record = build_record(OLDER, supersedes=None)
    for field in REQUIRED:
        if field not in record:
            return fail(f"built record missing {field}")
    validate_record(record)

    broken = dict(OLDER)
    broken.pop("deciding_rule", None)
    broken["rule_id"] = None
    try:
        build_record(broken, supersedes=None)
        return fail("record without deciding_rule was accepted")
    except LineageSchemaError as exc:
        print(f"schema_reject_deciding_rule={exc}")

    broken_tally = dict(OLDER)
    broken_tally["tally"] = None
    try:
        build_record(broken_tally, supersedes=None)
        return fail("record without tally was accepted")
    except LineageSchemaError as exc:
        print(f"schema_reject_tally={exc}")

    doc = seeded_log()
    older = doc["entries"][0]
    newer = commit_overturn(doc, NEWER, older["decision_id"], mark=True)
    older = doc["entries"][0]
    if older.get("status") != STATUS_SUPERSEDED:
        return fail(f"older status={older.get('status')} expected SUPERSEDED")
    if older.get("superseded_by") != newer["decision_id"]:
        return fail(
            f"older.superseded_by={older.get('superseded_by')} "
            f"expected {newer['decision_id']}"
        )
    if newer.get("status") != STATUS_LIVE:
        return fail(f"newer status={newer.get('status')} expected LIVE")
    if older["decision_id"] not in newer.get("supersedes"):
        return fail("newer.supersedes does not name the predecessor")
    scan = scan_live_contradictions(doc)
    print(json.dumps({"marked_scan": scan.as_dict()}, sort_keys=True))
    if scan.fired:
        return fail("contradiction scan FIRED after a marked overturn")
    if scan.live_count != 1:
        return fail(f"live_count={scan.live_count} expected 1 after mark")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "council-lineage.json"
        save_log(doc, path)
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["entries"][0]["superseded_by"] != "DEC-0351-B":
            return fail("saved log lost the supersession marker")
        md = path.with_suffix(".md").read_text(encoding="utf-8")
        if "SUPERSEDED by `DEC-0351-B`" not in md:
            return fail("markdown render omitted the supersession marker")

    print(
        json.dumps(
            {
                "question": QUESTION,
                "older_status": older["status"],
                "older_superseded_by": older["superseded_by"],
                "newer_supersedes": newer["supersedes"],
                "scan_fired": scan.fired,
                "required_fields": list(REQUIRED),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0351-probe1 lineage schema and supersession links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
