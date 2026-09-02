#!/usr/bin/env python3
"""BOTH-STATES probe for the gateway/lazy-activation architecture's central invariant.

INV-GW-1 "one door per event": for every hook event registered in the settings source of
truth, the number of registered host commands must be exactly 1.
INV-GW-2 "no uncosted battery": every gateway event must declare a numeric wall_cap, and
that wall_cap must be <= the host settings_timeout.

Detector control is MANDATORY: the checker is run against
  (a) the real repo state,
  (b) a KNOWN-GOOD synthetic state (must report 0 violations),
  (c) a KNOWN-BROKEN synthetic state (must report the violation).
A checker silent in both (b) and (c) measures nothing.

Also measures the already-shipped lazy-activation indexes.

Terminal state: SUCCESS:gwlazy-invariant / FAILED:gwlazy-invariant <reason>
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
OUT = REPO / "platform" / "architecture" / "_probe_gwlazy_invariant_out.json"
res: dict = {"probe": "gwlazy-invariant"}


# ---------------------------------------------------------------- checkers
def registrations_per_event(settings: dict) -> dict:
    out = {}
    for ev, lst in (settings.get("hooks") or {}).items():
        n = 0
        if isinstance(lst, list):
            for entry in lst:
                n += len((entry or {}).get("hooks", []) or [])
        out[ev] = n
    return out


def check_inv_gw1(settings: dict) -> list:
    return [
        {"event": ev, "registrations": n, "expected": 1}
        for ev, n in sorted(registrations_per_event(settings).items())
        if n != 1
    ]


def check_inv_gw2(manifest: dict) -> list:
    ev = manifest.get("events", manifest)
    viol = []
    for name, body in sorted((ev or {}).items()):
        if not isinstance(body, dict):
            continue
        wc = body.get("wall_cap", None)
        st = body.get("settings_timeout")
        if not isinstance(wc, (int, float)):
            viol.append({"event": name, "why": "wall_cap missing or non-numeric",
                         "wall_cap": wc, "settings_timeout": st})
        elif isinstance(st, (int, float)) and wc > st:
            viol.append({"event": name, "why": "wall_cap exceeds host timeout",
                         "wall_cap": wc, "settings_timeout": st})
    return viol


# ---------------------------------------------------------------- (a) real
srcs = {
    "agent-self/config/settings.json": REPO / "agent-self/config/settings.json",
    ".claude/settings.json": REPO / ".claude/settings.json",
}
real = {}
for label, p in srcs.items():
    if not p.exists():
        real[label] = {"MISSING": True}
        continue
    s = json.loads(p.read_text(encoding="utf-8"))
    per = registrations_per_event(s)
    v = check_inv_gw1(s)
    real[label] = {
        "events": len(per),
        "total_registrations": sum(per.values()),
        "registrations_per_event": per,
        "INV_GW1_violations": v,
        "INV_GW1_violation_count": len(v),
        "events_at_exactly_one": sum(1 for n in per.values() if n == 1),
    }
res["INV_GW1_real"] = real

man_p = REPO / "hooks/_dispatch/manifest.json"
man = json.loads(man_p.read_text(encoding="utf-8")) if man_p.exists() else {}
v2 = check_inv_gw2(man)
ev_rows = man.get("events", man)
res["INV_GW2_real"] = {
    "manifest": str(man_p.relative_to(REPO)).replace("\\", "/"),
    "gateway_events": sorted(k for k, b in (ev_rows or {}).items() if isinstance(b, dict)),
    "violations": v2,
    "violation_count": len(v2),
}

# ---------------------------------------------------------- (b)+(c) control
good_settings = {"hooks": {"Stop": [{"hooks": [{"command": "python dispatch.py Stop"}]}],
                           "PreToolUse": [{"hooks": [{"command": "python dispatch.py PreToolUse"}]}]}}
broken_settings = {"hooks": {"Stop": [{"hooks": [{"command": "a"}, {"command": "b"}]}],
                             "PreToolUse": [{"hooks": [{"command": "c"}]}],
                             "SessionEnd": [{"hooks": []}]}}
good_manifest = {"events": {"Stop": {"settings_timeout": 35, "wall_cap": 30, "checks": []}}}
broken_manifest = {"events": {"Stop": {"settings_timeout": 35, "wall_cap": "0", "checks": []},
                              "PreToolUse": {"settings_timeout": 15, "wall_cap": 60, "checks": []}}}

ctl = {
    "INV_GW1_known_good_violations": check_inv_gw1(good_settings),
    "INV_GW1_known_broken_violations": check_inv_gw1(broken_settings),
    "INV_GW2_known_good_violations": check_inv_gw2(good_manifest),
    "INV_GW2_known_broken_violations": check_inv_gw2(broken_manifest),
}
ctl["INV_GW1_detector_valid"] = (
    len(ctl["INV_GW1_known_good_violations"]) == 0
    and len(ctl["INV_GW1_known_broken_violations"]) == 2
)
ctl["INV_GW2_detector_valid"] = (
    len(ctl["INV_GW2_known_good_violations"]) == 0
    and len(ctl["INV_GW2_known_broken_violations"]) == 2
)
res["detector_control"] = ctl

# ------------------------------------------- shipped lazy-activation indexes
idx = {}
for label, rel in (
    ("skill-router/_index.json", "hooks/skill-router/_index.json"),
    ("semantic-router/index/meta.json", "hooks/semantic-router/index/meta.json"),
    ("semantic-router/index/vecs.f32", "hooks/semantic-router/index/vecs.f32"),
    ("recall-inject/index/recall_index.json", "hooks/recall-inject/index/recall_index.json"),
    ("capability-catalog/catalog.json", "hooks/capability-catalog/catalog.json"),
    ("platform/schema/ARTIFACT-CLASS-REGISTRY.json", "platform/schema/ARTIFACT-CLASS-REGISTRY.json"),
    ("platform/schema/workflow-dsl.capability-map.json", "platform/schema/workflow-dsl.capability-map.json"),
):
    p = REPO / rel
    if not p.exists():
        idx[label] = {"MISSING": True}
        continue
    e = {"bytes": p.stat().st_size}
    if p.suffix == ".json":
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            e["top_keys"] = sorted(d.keys())[:12] if isinstance(d, dict) else f"list[{len(d)}]"
            for k in ("entries", "skills", "items", "classes", "capabilities", "notes", "records"):
                if isinstance(d, dict) and isinstance(d.get(k), (list, dict)):
                    e[f"n_{k}"] = len(d[k])
        except Exception as exc:
            e["parse_error"] = str(exc)[:120]
    idx[label] = e
res["shipped_lazy_indexes"] = idx

OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
print(json.dumps(res, indent=2)[:8000])
print(f"\nwrote {OUT}")
ok = ctl["INV_GW1_detector_valid"] and ctl["INV_GW2_detector_valid"]
print("SUCCESS:gwlazy-invariant" if ok else "FAILED:gwlazy-invariant detector-control-failed")
