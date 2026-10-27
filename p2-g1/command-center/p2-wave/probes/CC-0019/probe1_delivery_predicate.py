#!/usr/bin/env python3
"""CC-0019 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the record conservation identity (2091 inputs = 1894 emitted + 175 merged + 22 dropped), record row completeness (claim_id, confidence vocabulary, source lineage), and the path:line:quote anchor policy.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/CC-0019.json"
UNIT = "CC-0019"
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

    cons = doc.get("conservation") or {}
    recs = doc.get("records") or []
    dropped = doc.get("dropped") or []
    emitted, merged, drop = int(cons.get("emitted", -1)), int(cons.get("merged", -1)), int(cons.get("dropped", -1))
    inputs = int(cons.get("inputs", -1))
    check(emitted + merged + drop == inputs, "conservation identity fails",
          "%d+%d+%d != %s" % (emitted, merged, drop, cons.get("inputs")))
    check(len(recs) == emitted, "records != emitted", "%d vs %s" % (len(recs), cons.get("emitted")))
    check(len(dropped) == drop, "dropped rows != dropped count", "%d vs %s" % (len(dropped), cons.get("dropped")))
    check("inputs = emitted + merged + dropped" in str(cons.get("identity", "")),
          "conservation identity statement drift", str(cons.get("identity")))
    vocab = {"HIGH", "MEDIUM", "LOW"}
    bad_conf = [r.get("claim_id") for r in recs[:200] if str(r.get("confidence")) not in vocab]
    check(not bad_conf, "confidence outside vocabulary", str(bad_conf[:3]))
    no_lineage = [r.get("claim_id") for r in recs[:200] if not (r.get("source_lineage") or [])]
    check(not no_lineage, "records missing source_lineage", str(no_lineage[:3]))
    check(all(str(r.get("claim_id", "")).startswith("CLM-") for r in recs[:200]),
          "claim_id prefix drift")
    ap = str(doc.get("anchor_policy", ""))
    check("path:line" in ap and "quote" in ap, "anchor policy drift", ap[:80])
    check(len(recs) > 0 and all(r.get("claim_id") and isinstance(r.get("rank"), dict) for r in recs[:50]),
          "first 50 records lack claim_id or rank block")

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
