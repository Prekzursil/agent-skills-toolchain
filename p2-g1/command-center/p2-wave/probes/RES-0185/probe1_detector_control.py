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
"""Detector control: the three planted rows must be classified exactly as
recorded (single->single-source, four-class->not, unsupported->UNSUPPORTED),
and headline counts must exclude plants."""
doc = load()
det = doc.get("detector_control") or {}
xtab = doc.get("cross_tab") or []
byid = {r.get("id"): r for r in xtab}
single = byid.get(det.get("single_plant_id"))
need(single is not None, "single-source plant missing from map")
need(single.get("single_source") is True and det.get("single_plant_marked_single_source") is True,
     "single-source plant not marked single-source")
four = byid.get(det.get("four_class_plant_id"))
need(four is not None and four.get("class_count") == 4, "four-class plant wrong class_count")
need(four.get("single_source") is False and det.get("four_class_plant_marked_single_source") is False,
     "four-class plant marked single-source")
uns = byid.get(det.get("unsupported_plant_id"))
need(uns is not None, "unsupported plant missing from map")
need(str(uns.get("support_status", "")).upper()
     == str(det.get("unsupported_plant_status", "")).upper(),
     "unsupported plant status "
     f"{uns.get('support_status')!r} != recorded {det.get('unsupported_plant_status')!r}")
need(det.get("pass") is True, "detector_control.pass is not true")
harv = doc.get("harvest_frame") or {}
need(harv.get("plants_excluded_from_headline") is True, "plants not excluded from headline")
plants = {det.get("single_plant_id"), det.get("four_class_plant_id"), det.get("unsupported_plant_id")}
real = [r for r in xtab if r.get("id") not in plants]
need(sum(1 for r in real if r.get("single_source")) == doc.get("single_source_count"),
     "single_source_count != recount excluding plants")
uns_rec = sum(1 for r in real
              if str(r.get("support_status", "")).upper() == "UNSUPPORTED")
need(uns_rec == doc.get("unsupported_count"),
     f"unsupported_count {doc.get('unsupported_count')} != recount {uns_rec}")
multi_rec = sum(1 for r in real
                if str(r.get("support_status", "")).upper() == "MULTI")
need(multi_rec == doc.get("multi_count"),
     f"multi_count {doc.get('multi_count')} != recount {multi_rec}")
ok("detector control", len(xtab), "rows incl 3 plants")
