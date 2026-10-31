#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0184"
OUT = (REPO / "command-center/research/evidence-quality/RES-0184-evidence-threshold-by-claim-severity.json").resolve()


def fail(msg):
    print(f"FAILED:{UID}-probe {msg}")
    raise SystemExit(1)


def ok(*parts):
    print("PROBE-OK", UID, *parts)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"artifact unreadable: {type(exc).__name__}: {exc}")


def need(cond, msg):
    if not cond:
        fail(msg)
"""Re-verify the 20-claim rescore: below-bar counts, high-severity list,
and the NC-SEVERITY-NOT-FLAT negative control, from the recorded rows."""
doc = load()
rows = doc.get("rescore", {}).get("rows") or []
need(len(rows) == 20, f"rescore rows n={len(rows)} expected 20")


below_rows = [r for r in rows if r.get("meets_bar") is False]
need(doc["rescore"].get("below_bar_count") == len(below_rows),
     "rescore.below_bar_count != recomputed below rows")
ans = doc.get("answer") or {}
need(ans.get("below_bar_count") == len(below_rows),
     "answer.below_bar_count != recomputed below rows")
high_below = sorted(r["claim_id"] for r in below_rows
                    if str(r.get("severity", "")).upper() in ("P0", "P1"))
need(high_below == sorted(ans.get("high_severity_below_ids") or []),
     "answer.high_severity_below_ids != recomputed")
need(len(ans.get("high_severity_below_ids") or []) >= 1,
     "negative control: no high-severity claim below bar -> calibration UNINFORMATIVE")
bars = doc.get("bars") or {}
p0, p3 = bars.get("P0") or {}, bars.get("P3") or {}
need((p0.get("min_independent_sources") or 0) > (p3.get("min_independent_sources") or 99),
     "bars flat across severity: P0 not strictest")
need(p0.get("executable_mandatory") is True and p0.get("lineage_mandatory") is True,
     "P0 bar lost executable/lineage mandate")
ncs = doc.get("negative_controls") or []
nc = next((n for n in ncs if "NOT-FLAT" in str(n.get("id", "")).upper()
           or "SEVERITY" in str(n.get("id", "")).upper()), None)
need(nc is not None, "NC-SEVERITY-NOT-FLAT control missing")
need(nc.get("fired_on_bad_state", nc.get("fired")) is True,
     "NC-SEVERITY-NOT-FLAT did not fire")
need(doc.get("calibration") == "INFORMATIVE", "calibration not INFORMATIVE")
ok("rescore", len(rows), "below", len(below_rows), "high-below",
   len(ans.get("high_severity_below_ids") or []))
