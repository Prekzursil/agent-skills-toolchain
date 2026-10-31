#!/usr/bin/env python3
"""BLD-0061 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the two recorded contradictions (B09 vs B10 lanes, both probes escalated), the probe-wins-over-tally overrule, and the negative-control both-states rows.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0061.json"
UNIT = "BLD-0061"
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

    ct = doc.get("contradictions") or []
    check(len(ct) == 2, "contradiction rows != 2", str(len(ct)))
    ids_ = [str(c.get("id")) for c in ct]
    check(len(set(ids_)) == 2, "contradiction ids not unique")
    for c in ct:
        left, right = c.get("left") or {}, c.get("right") or {}
        check(str(left.get("lane")) != str(right.get("lane")), "contradiction lanes not distinct", str(c.get("id")))
        check(str(left.get("id")) != str(right.get("id")), "contradiction side ids equal", str(c.get("id")))
        for side in (left, right):
            anchor = str(side.get("anchor", ""))
            check("probes/BLD-0061/fixtures/lanes/" in anchor and anchor.rsplit(":", 1)[-1].isdigit(),
                  "anchor not path:line under planted lanes", anchor[-60:])
        check(c.get("escalated_with_both_probes") is True, "not escalated with both probes", str(c.get("id")))
        check(str(c.get("kind")) in {"count", "verdict"}, "kind outside vocabulary", str(c.get("kind")))
    po = doc.get("probe_wins_over_tally") or {}
    to = doc.get("tally_overruled") or []
    check(po.get("applied") is True and int(po.get("overruled_count", -1)) == len(to) >= 1,
          "probe-wins overrule bookkeeping drift", "applied=%s overruled=%s/%d" % (po.get("applied"), po.get("overruled_count"), len(to)))
    check("probe" in str(po.get("rule", "")).lower() and "tally" in str(po.get("rule", "")).lower(),
          "probe-wins rule text drift", str(po.get("rule"))[:60])
    ncs = doc.get("negative_controls") or []
    check(len(ncs) >= 1 and all(c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True for c in ncs),
          "negative controls not both-states", str(len(ncs)))
    settle = (ct[0].get("settlement") or ct[0].get("raw_source") or ct[0].get("resolution") or {})
    check(int(settle.get("parsed_value", -1)) == 28, "settlement parsed_value != 28", str(settle.get("parsed_value")))
    check(isinstance(settle.get("source"), str) and "fixtures/sources/" in str(settle.get("source")),
          "settlement source not a fixture path", str(settle.get("source"))[:80])

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
