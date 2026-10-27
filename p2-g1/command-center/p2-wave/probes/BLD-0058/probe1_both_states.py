#!/usr/bin/env python3
"""BLD-0058 probe1 - structural + sentinel delivery predicate (live, fail-closed).

Checks the 10x scale chain against the live catalog (2007 units x 10 = 20070), the both-states schedule identities, the 429/529 classification table with its opposite responses, and the binding-RPM rule (NOT-CHECKED rows excluded).
Recreated 2026-10-25 (wave-2 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
OUT = REPO / "command-center/receipts/BLD-0058.json"
UNIT = "BLD-0058"
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

    import json as _json
    scale = doc.get("scale") or {}
    cat = _json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    n_live = len(cat.get("work_units") or [])
    check(int(scale.get("baseline_n", -1)) == 2007 == n_live,
          "baseline_n != live catalog length", "recorded=%s live=%d" % (scale.get("baseline_n"), n_live))
    check(int(scale.get("scaled_n", -1)) == int(scale.get("baseline_n", 0)) * int(scale.get("factor", 0)) == 20070,
          "scaled chain != baseline*factor", str(scale))
    bs = (doc.get("schedule") or {}).get("both_states") or {}
    check(int(bs.get("burst_200", -1)) + int(bs.get("burst_429", -1)) == int(bs.get("n_10x", -1)) == 20070,
          "burst arm identity fails", str(bs))
    check(int(bs.get("stagger_200", -1)) == 20070 and int(bs.get("stagger_429", -1)) == 0,
          "stagger arm identity fails", str(bs))
    check(bs.get("vacuous") is False, "both-states marked vacuous")
    rows = doc.get("error_classes") or []
    check(len(rows) == 2, "error class rows != 2", str(len(rows)))
    by = {int(r.get("http_status")): r for r in rows}
    check(set(by) == {429, 529}, "error classes are not exactly 429/529", str(sorted(by)))
    if set(by) == {429, 529}:
        check(by[429].get("class") == "OUR_ARRIVAL_RATE" and "stagger" in str(by[429].get("scheduler_response", "")),
              "429 classified wrong", str(by[429].get("class")))
        check(by[529].get("class") == "VENDOR_OVERLOAD" and "keep-concurrency" in str(by[529].get("scheduler_response", "")),
              "529 classified wrong", str(by[529].get("class")))
        check(int(by[529].get("concurrency_after_correct", -1)) == int(by[529].get("concurrency_before", -2))
              and int(by[529].get("concurrency_after_naive_control", -1)) < int(by[529].get("concurrency_before", -2)),
              "529 keep-concurrency vs naive-throttle asymmetry missing", str(by[529]))
    quotas = doc.get("quotas") or []
    eligible = [q for q in quotas if str(q.get("unit")) == "rpm"
                and str(q.get("status")) in {"DOCUMENTED", "MEASURED"} and isinstance(q.get("numeric_value"), int)]
    check(len(eligible) >= 2, "eligible DOCUMENTED/MEASURED rpm rows < 2", str(len(eligible)))
    binding = doc.get("binding_constraint") or {}
    check(min(q["numeric_value"] for q in eligible) == int(binding.get("numeric_value", -1)) == 500,
          "binding rpm is not the eligible min", str(binding.get("numeric_value")))
    check(str(binding.get("status")) == "MEASURED", "binding row not MEASURED", str(binding.get("status")))
    check(all(str(q.get("status")) == "NOT-CHECKED" for q in quotas if q not in eligible),
          "excluded rows are not NOT-CHECKED")
    check((HERE / "sim.py").is_file(), "instrument sim.py missing")

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
