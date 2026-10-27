#!/usr/bin/env python3
"""CNF-0070 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks all six citation rows: failure_class/verdict pairing, capture timestamp at or before the citation date for every archived corroboration, sha format, and the summary verdict counts.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/confirmation/CNF-0070-archival-corroboration.json"
UNIT = "CNF-0070"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main() -> int:
    fails = []
    notes = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(label + (": " + detail if detail else ""))

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print("FAILED:%s-probe1 artifact unreadable/unparseable: %s" % (UNIT, type(exc).__name__))
        return 1
    if not isinstance(doc, dict):
        print("FAILED:%s-probe1 artifact is not a JSON object" % UNIT)
        return 1

    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact empty")
    minb = int(doc.get("min_bytes_threshold") or 0)
    check(OUT.stat().st_size >= minb, "below min_bytes_threshold",
          "%s < %s" % (OUT.stat().st_size, minb))
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel absent from artifact text")

    import datetime as _dt
    cits = doc.get("citations") or []
    summ = doc.get("summary") or {}
    check(len(cits) == 6, "citation rows != 6", str(len(cits)))
    ids_ = [str(c.get("id")) for c in cits]
    check(len(set(ids_)) == 6, "citation ids not unique")
    pair = {"source-changed": "was-true-then-changed", "never-supported": "never-supported",
            "no-snapshot-available": "no-snapshot-available"}
    vc = {}
    late = []
    for c in cits:
        cls, verd = str(c.get("failure_class")), str(c.get("verdict"))
        check(pair.get(cls) == verd, "failure_class/verdict pair drift", "%s: %s/%s" % (c.get("id"), cls, verd))
        vc[verd] = vc.get(verd, 0) + 1
        ac = c.get("archived_corroboration") or {}
        ts, cd = str(ac.get("capture_timestamp") or ""), str(c.get("citation_date") or "")
        if verd == "was-true-then-changed":
            check(bool(ts) and bool(cd), "changed verdict without capture/citation dates", str(c.get("id")))
            if ts and cd:
                if _dt.date.fromisoformat(ts[:10]) > _dt.date.fromisoformat(cd):
                    late.append(c.get("id"))
            check(str(ac.get("sha256", "")).strip() == "" or len(str(ac.get("sha256"))) == 64,
                  "recorded sha not hex64", str(c.get("id")))
            check(int(ac.get("quote_offset", -1)) >= 0 and str(ac.get("located_quote", "")).strip(),
                  "archived row missing quote/offset", str(c.get("id")))
            check(str(ac.get("snapshot_url", "")).startswith("fixture://"), "snapshot url form", str(ac.get("snapshot_url"))[:40])
        else:
            check(not ac.get("capture_timestamp"), "non-archived verdict carries a capture timestamp", str(c.get("id")))
    check(not late, "a capture timestamp is AFTER its citation date", str(late))
    check(vc == (summ.get("verdict_counts") or {}), "summary verdict_counts drift",
          "rows=%s summary=%s" % (vc, summ.get("verdict_counts")))
    check(int(summ.get("citation_count", -1)) == 6 and summ.get("every_archived_corroboration_timely") is True,
          "summary counters drift", str(summ.get("citation_count")))
    check(vc.get("never-supported") == int(summ.get("never_supported_count", -1))
          and vc.get("no-snapshot-available") == int(summ.get("no_snapshot_available_count", -1))
          and vc.get("was-true-then-changed") == int(summ.get("was_true_then_changed_count", -1)),
          "summary per-verdict counters drift")

    report = {
        "probe": "probe1-delivery-predicate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:%s-probe1 %s" % (UNIT, "; ".join(fails)))
        return 1
    print("SUCCESS:%s-probe1 delivery predicate holds" % UNIT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
