#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "RES-0185"
OUT = (REPO / "command-center/research/evidence-quality/RES-0185-evidence-map-coverage-holes.json").resolve()


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
"""Independent recount by a DIFFERENT mechanism: sum the per-class fields and
compare against class_count / single_class flags row by row (two counters)."""
doc = load()
xtab = doc.get("cross_tab") or []
need(len(xtab) == doc.get("program_conclusion_count") + doc.get("plant_count"),
     f"cross_tab rows {len(xtab)} != program+plants")
META = {"id", "class_count", "independent_source_count", "single_class",
        "single_source", "support_status", "plant", "conclusion", "text"}
class_fields = [k for k in xtab[0] if k not in META] if xtab else []
need(len(class_fields) >= 14, f"class vocabulary n={len(class_fields)} unexpectedly small")
bad = 0
for r in xtab:
    distinct = sum(1 for f in class_fields if f != "unclassified"
                   and int(r.get(f, 0) or 0) > 0)
    if distinct != r.get("class_count"):
        bad += 1
need(bad == 0, f"{bad} rows where distinct-class recount != class_count")
need(sum(1 for r in xtab if str(r.get("support_status", "")) == "SINGLE-SOURCE")
     == sum(1 for r in xtab if r.get("independent_source_count") == 1),
     "SINGLE-SOURCE partition != independent_source_count==1 rows")
need(all(str(r.get("support_status", "")) != "SINGLE-CLASS"
         or r.get("class_count") == 1 for r in xtab),
     "SINGLE-CLASS row with class_count != 1 (partition implication broken)")
det = doc.get("detector_control") or {}
plants = {det.get("single_plant_id"), det.get("four_class_plant_id"),
          det.get("unsupported_plant_id")}
real_rows = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real_rows if r.get("class_count") == 1) == doc.get("single_class_count"),
     "single_class_count != recount excluding plants")
need(sum(1 for r in real_rows if str(r.get("support_status", "")) == "MULTI") == doc.get("multi_count"),
     "multi_count != SUPPORT status MULTI recount")
conc = doc.get("conclusions") or []
need(len(conc) >= len(xtab) - 3, "conclusions array materially smaller than map")
ok("independent recount", len(xtab), "rows; per-class sums agree with class_count")
