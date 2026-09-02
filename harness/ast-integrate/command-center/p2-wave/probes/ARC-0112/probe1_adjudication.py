#!/usr/bin/env python3
"""Probe 1: every failing record is classified; none left as an unexplained count."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import golden as G  # noqa: E402

REPORT = REPO / G.OUT_REL


def main() -> int:
    if not REPORT.is_file() or REPORT.stat().st_size <= 0:
        print("FAILED:ARC-0112-probe1 report absent")
        return 1
    doc = json.loads(REPORT.read_text(encoding="utf-8"))
    live = G.collect_failures()
    adj_live = G.adjudicate(live)
    adj_doc = doc.get("adjudication") or {}
    failures = doc.get("failures") or []

    unexplained_doc = 0
    directions = []
    for row in failures:
        if not isinstance(row, dict):
            unexplained_doc += 1
            continue
        direction = str(row.get("direction") or "")
        citation = str(row.get("citation") or "")
        reason = str(row.get("reason") or "")
        fid = str(row.get("id") or "")
        if direction not in {"artifact-wrong", "schema-wrong"} or not citation or not reason or not fid:
            unexplained_doc += 1
        directions.append(direction)

    if unexplained_doc != 0:
        print(f"FAILED:ARC-0112-probe1 unexplained_in_report={unexplained_doc}")
        return 1
    if adj_live["unexplained"] != 0:
        print(f"FAILED:ARC-0112-probe1 live unexplained={adj_live['unexplained']}")
        return 1
    if adj_live["classified"] != adj_live["failing_records"]:
        print(
            "FAILED:ARC-0112-probe1 live classified "
            f"{adj_live['classified']} != {adj_live['failing_records']}"
        )
        return 1
    if int(adj_doc.get("unexplained", 1)) != 0:
        print(f"FAILED:ARC-0112-probe1 doc unexplained={adj_doc.get('unexplained')}")
        return 1
    if int(adj_doc.get("failing_records", -1)) != len(failures):
        print(
            "FAILED:ARC-0112-probe1 failing_records "
            f"{adj_doc.get('failing_records')} != len(failures) {len(failures)}"
        )
        return 1
    if int(adj_doc.get("failing_records", -1)) != adj_live["failing_records"]:
        print(
            "FAILED:ARC-0112-probe1 stale report "
            f"doc={adj_doc.get('failing_records')} live={adj_live['failing_records']}"
        )
        return 1
    if adj_doc.get("computed_not_asserted") is not True:
        print("FAILED:ARC-0112-probe1 computed_not_asserted missing")
        return 1

    live_ids = [str(r.get("id")) for r in live]
    doc_ids = [str(r.get("id")) for r in failures]
    if live_ids != doc_ids:
        print(
            "FAILED:ARC-0112-probe1 failure-id drift "
            f"doc={doc_ids} live={live_ids}"
        )
        return 1

    # Detector control: defaults-only fields must be reported (ARC-0083).
    defaults = [r for r in failures if r.get("id") == "F-ITEMS-DEFAULTS-ONLY"]
    if len(defaults) != 1:
        print(f"FAILED:ARC-0112-probe1 defaults-only finding missing n={len(defaults)}")
        return 1
    fields = defaults[0].get("fields") or []
    if len(fields) < 9:
        print(f"FAILED:ARC-0112-probe1 defaults-only fields {fields} (expected >=9)")
        return 1

    art = directions.count("artifact-wrong")
    sch = directions.count("schema-wrong")
    print(
        "adjudicated="
        f"{len(failures)} unexplained=0 artifact-wrong={art} schema-wrong={sch} "
        f"defaults-only-fields={len(fields)} live_match=True"
    )
    print("SUCCESS:ARC-0112-probe1 adjudication completeness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
