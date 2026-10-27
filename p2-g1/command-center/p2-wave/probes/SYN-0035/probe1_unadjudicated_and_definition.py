#!/usr/bin/env python3
"""@DOC
Shard 20 wave-2 resume (builder): live named probe. Exit 0 = green.
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UID = "SYN-0035"
OUT = (REPO / "command-center/synthesis/SYN-0035.calibration-report.json").resolve()


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
"""Unadjudicated claims are counted, never imputed; every band row states n;
band intervals come from the written definition and contain the band's point."""
doc = load()
unadj = doc.get("unadjudicated") or {}
need(unadj.get("combined") == unadj.get("live", -1) + unadj.get("synthetic", -1),
     "unadjudicated combined != live + synthetic")
syn_unadj = sum(1 for p in (doc.get("planted_items") or [])
                if str(p.get("set_id", "")).startswith("synthetic-unadjudicated"))
need(doc.get("unadjudicated_count") == syn_unadj,
     f"unadjudicated_count {doc.get('unadjudicated_count')} "
     f"!= synthetic-unadjudicated set n={syn_unadj}")
min_n = doc.get("min_n_to_score", 5)
bands = doc.get("bands") or []
need(len(bands) >= 4, f"bands n={len(bands)}")
pp = doc.get("point_p") or {}
for b in bands:
    name = b.get("band")
    need(isinstance(b.get("n"), int), f"band {name}: n not stated")
    need(b.get("n_too_small") == (b.get("n", 0) < min_n),
         f"band {name}: n_too_small flag inconsistent with min_n_to_score={min_n}")
    oh = b.get("observed_hit_rate") or {}
    if oh.get("denominator"):
        need(abs(oh.get("value", -1) - oh["numerator"] / oh["denominator"]) < 1e-9,
             f"band {name}: hit rate != numerator/denominator")
    pi = b.get("nominal_interval") or []
    pt = pp.get(name)
    if pi and pt is not None:
        need(pi[0] <= pt <= pi[1], f"band {name}: point {pt} outside written interval {pi}")
    need(b.get("interval_source"), f"band {name}: interval_source (written definition) missing")
ok("unadjudicated counted not imputed;", len(bands), "bands state n + written intervals")
