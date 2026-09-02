#!/usr/bin/env python3
"""Probe 2: planted drift / rewrite / gone / stable (detector control).

Insert a line above a known anchor -> LINE-MOVED not STABLE.
Change the anchored line -> CONTENT-CHANGED.
Delete the file -> FILE-GONE.
Unchanged anchor stays STABLE (silent on the known-good).
Both-states: STABLE and LINE-MOVED remain distinct classes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import CLASSES, receipt_body, run_campaign  # noqa: E402

ART = REPO / "command-center/receipts/SYN-0018.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0018-probe2 {msg}")
    return 1


def main() -> int:
    campaign = run_campaign()
    rows = campaign["anchors"]
    by_id = {str(r["id"]): r for r in rows}
    want = {
        "CLAIM-STABLE-001": "STABLE",
        "CLAIM-MOVED-001": "LINE-MOVED",
        "CLAIM-REWRITE-001": "CONTENT-CHANGED",
        "CLAIM-GONE-001": "FILE-GONE",
    }
    for cid, expected in want.items():
        got = by_id.get(cid, {}).get("class")
        if got != expected:
            return fail(f"{cid} class={got} expected={expected}")

    moved = by_id["CLAIM-MOVED-001"]
    if moved["class"] == "STABLE":
        return fail("planted-drift-classified-STABLE")
    if moved.get("report_line") == moved.get("capture_line"):
        return fail("planted-drift-line-unchanged")

    rewritten = by_id["CLAIM-REWRITE-001"]
    if rewritten["class"] != "CONTENT-CHANGED":
        return fail("planted-rewrite-not-CONTENT-CHANGED")

    gone = by_id["CLAIM-GONE-001"]
    if gone.get("report_byte_range") is not None:
        return fail("gone-has-report-byte-range")

    stable = by_id["CLAIM-STABLE-001"]
    if stable.get("capture_byte_range") != stable.get("report_byte_range"):
        return fail("stable-byte-range-shifted")

    classes_seen = {str(r["class"]) for r in rows}
    if classes_seen != set(CLASSES):
        return fail(f"class-set {sorted(classes_seen)}")
    if "STABLE" in classes_seen and "LINE-MOVED" in classes_seen:
        if by_id["CLAIM-STABLE-001"]["class"] == by_id["CLAIM-MOVED-001"]["class"]:
            return fail("both-states-collapsed")

    counts = campaign["class_counts"]
    totals = {counts[c]["total"] for c in CLASSES}
    if len(totals) != 1:
        return fail(f"denominator-mismatch {counts}")
    total = next(iter(totals))
    if total != len(rows):
        return fail(f"total={total} rows={len(rows)}")
    for name in CLASSES:
        as_string = counts[name]["as_string"]
        if not as_string.endswith(f"/{total}"):
            return fail(f"{name} missing-total-denominator {as_string}")

    for row in rows:
        for key in ("capture_sha", "report_sha", "class"):
            if not row.get(key):
                return fail(f"{row.get('id')} missing {key}")
        if row["class"] != "FILE-GONE" and not row.get("report_byte_range"):
            return fail(f"{row['id']} missing report_byte_range")
        if row["recipe"] != "git cat-file -p":
            return fail(f"{row['id']} recipe={row.get('recipe')}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt-missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    body = receipt_body(doc)
    rec_by_id = {str(a.get("id")): a for a in (body.get("anchors") or [])}
    for cid, expected in want.items():
        rec = rec_by_id.get(cid) or {}
        if rec.get("class") != expected:
            return fail(f"receipt {cid} class={rec.get('class')}")
        if rec.get("recipe") != "git cat-file -p":
            return fail(f"receipt {cid} recipe")

    rec_counts = body.get("class_counts") or {}
    for name in CLASSES:
        cell = rec_counts.get(name) or {}
        if str(cell.get("as_string") or "").split("/")[-1:] != [str(total)]:
            return fail(f"receipt {name} as_string={cell.get('as_string')}")

    summary = {
        "probe": "probe2-planted",
        "unit_id": "SYN-0018",
        "stable_silent": True,
        "planted_drift_line_moved": True,
        "planted_rewrite_content_changed": True,
        "planted_delete_file_gone": True,
        "both_states_not_collapsed": True,
        "classes": {k: counts[k]["as_string"] for k in CLASSES},
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "drift=LINE-MOVED rewrite=CONTENT-CHANGED gone=FILE-GONE "
        "stable=STABLE both-states=distinct"
    )
    print("SUCCESS:SYN-0018-probe2 planted drift/rewrite/gone/stable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
