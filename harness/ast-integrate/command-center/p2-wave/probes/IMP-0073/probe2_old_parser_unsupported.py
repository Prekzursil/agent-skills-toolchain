#!/usr/bin/env python3
"""Probe 2: v1 parser given a v2 index returns UNSUPPORTED, not a truncated list.

Signal 2 of IMP-0073. Method: migrate the LIVE marketplace.json to v2, then
parse_index(..., parser_version=1). File record count is compared against a
lenient v1 parse that only reads plugins[]/packages[] — those counts disagree,
which is the silent-drop hazard. Independent of probe 1's synthetic round-trip.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.marketplace.index_migrate import (  # noqa: E402
    COMPATIBILITY_WINDOW_VERSIONS,
    UNSUPPORTED,
    file_record_count,
    lenient_v1_parse,
    migrate,
    parse_index,
    schema_version_of,
)
from tools.marketplace.manifest_reader import live_path, load_manifest  # noqa: E402
from tools.marketplace.tests import test_index_migrate as T  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0073.json"


def _receipt_ok() -> str | None:
    if not ART.is_file():
        return "receipt missing"
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return f"receipt unparseable {exc}"
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"self-declared {doc.get('state')}"
    if "SUCCESS:IMP-0073" not in text:
        return "sentinel absent"
    window = doc.get("compatibility_window_versions")
    if window != COMPATIBILITY_WINDOW_VERSIONS:
        return f"receipt window {window!r} != {COMPATIBILITY_WINDOW_VERSIONS}"
    return None


def main() -> int:
    T.test_old_parser_declares_unsupported()

    live = load_manifest(live_path(REPO))
    src = copy.deepcopy(live.data)
    src_v = schema_version_of(src)
    v2 = migrate(src, src_v + 1)
    file_n = file_record_count(v2)
    honest = parse_index(v2, parser_version=src_v)
    lenient = lenient_v1_parse(v2)
    counts_disagree = len(lenient) != file_n
    refused = (
        honest.status == UNSUPPORTED
        and honest.records is None
        and honest.parsed_record_count is None
        and honest.file_record_count == file_n
    )

    report = {
        "probe": "probe2-old-parser-unsupported",
        "unit_id": "IMP-0073",
        "live_path": ".claude-plugin/marketplace.json",
        "live_schema_version": src_v,
        "v2_schema_version": schema_version_of(v2),
        "compatibility_window_versions": COMPATIBILITY_WINDOW_VERSIONS,
        "file_record_count": file_n,
        "lenient_v1_parsed_count": len(lenient),
        "lenient_disagrees_with_file": counts_disagree,
        "honest_status": honest.status,
        "honest_parsed_record_count": honest.parsed_record_count,
        "honest_records_is_none": honest.records is None,
        "honest_reason": honest.reason,
        "pass": refused and counts_disagree and file_n > 0,
    }
    print(json.dumps(report, sort_keys=True))
    if file_n <= 0:
        print("FAILED:IMP-0073-probe2 live v2 file_record_count is 0")
        return 1
    if not counts_disagree:
        print("FAILED:IMP-0073-probe2 lenient parse did not drop records")
        return 1
    if not refused:
        print("FAILED:IMP-0073-probe2 honest parser did not declare UNSUPPORTED")
        return 1
    err = _receipt_ok()
    if err:
        print(f"FAILED:IMP-0073-probe2 {err}")
        return 1
    print("SUCCESS:IMP-0073-probe2 old parser UNSUPPORTED; count disagreement proves drop hazard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
