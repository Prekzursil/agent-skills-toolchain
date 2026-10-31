#!/usr/bin/env python3
"""BLD-0049 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the 7-ingress census (instrument side all FENCED, production side UNFENCED x4 / ABSENT-SITE x3), canary coverage of every ingress id, and the fence.py:29 instrument anchor.
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0049.json"
UNIT = "BLD-0049"
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

    ing = doc.get("ingresses") or []
    check(len(ing) == 7, "ingress rows != 7", str(len(ing)))
    ids_ = [str(i.get("id")) for i in ing]
    check(len(set(ids_)) == 7, "ingress ids not unique")
    check(all(str(i.get("instrument_fencing")).upper() == "FENCED" for i in ing),
          "instrument_fencing not all FENCED")
    hist = {}
    for i in ing:
        hist[str(i.get("production_fencing"))] = hist.get(str(i.get("production_fencing")), 0) + 1
    check(hist == {"UNFENCED": 4, "ABSENT-SITE": 3}, "production_fencing histogram drift", json.dumps(hist))
    check(all(str(i.get("search", "")).strip() for i in ing), "ingress row missing search text")
    can = doc.get("canary_results") or []
    check(len(can) == 7 and {str(c.get("ingress_id")) for c in can} == set(ids_),
          "canary rows do not cover exactly the 7 ingress ids", str(len(can)))
    check(all(c.get("canary_visible_as_data") is True for c in can),
          "canary_visible_as_data not true for every ingress")
    plants = doc.get("production_plants") or []
    check(len(plants) == 4 and all(str(p.get("ingress_id")) in ids_ for p in plants),
          "production plants != 4 rows within ingress ids", str(len(plants)))
    check(all(p.get("canary_in_output") is True and p.get("fenced") is False for p in plants),
          "production plant rows inconsistent with UNFENCED claim")
    tests = doc.get("tests") or []
    check(len(tests) == 2 and all(t.get("result") == "PASS" for t in tests),
          "recorded tests != 2 PASS rows", str([(t.get("id"), t.get("result")) for t in tests]))
    fence = HERE / "fence.py"
    check(fence.is_file(), "instrument fence.py missing", str(fence))
    if fence.is_file():
        line29 = fence.read_text(encoding="utf-8").splitlines()[28] if len(fence.read_text(encoding="utf-8").splitlines()) >= 29 else ""
        check("def fence_untrusted" in line29 or "FENCE" in line29,
              "fence.py:29 does not carry the fence construct", line29.strip()[:60])

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
