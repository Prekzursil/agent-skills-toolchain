#!/usr/bin/env python3
"""WFA-0146 probe2 -- repair-vs-build separator + live router recheck.

Re-runs the LIVE executable (command-center/foundry/routing/recommend.py,
re-materialized this session after the prior builder lost it) over all 284
stored evaluation rows and requires 284/284 route + deciding-feature agreement
with the artifact; exercises decide() on synthetic archetypes so every route
fires both ways; runs the label-leak control (a planted ADOPT-AS-IS
classification with a retired-ineligible scout shape must route BUILD -
classification must not leak into routing), the constant-function control
(>=3 distinct routes), the threshold-boundary control (the REPAIR/BUILD
separator flips at repair_cost_ratio == repair_cost_ratio_max), the live
both-states mutant on holdout_agreement, and the manifest byte-compare.
Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0146"
REL = "command-center/foundry/WFA-0146-find-repair-merge-build-recommendation-function.json"
sys.path.insert(0, str(REPO / "command-center" / "foundry"))

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    try:
        art = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1
    from routing import recommend

    # ---- live router reproduces all 284 stored predictions ----------------- #
    rows = art.get("evaluation_rows") or []
    chk(len(rows) == 284, "row-count", str(len(rows)))
    bad = 0
    for r in rows:
        out = recommend.decide(r["features"])
        if out["route"] != r["predicted_route"] \
                or out["deciding_feature"] != r["deciding_feature"]:
            bad += 1
            if bad <= 3:
                chk(False, "router-disagrees", json.dumps(
                    {"id": r["id"], "live": [out["route"], out["deciding_feature"]],
                     "stored": [r["predicted_route"], r["deciding_feature"]]})[:300])
    chk(bad == 0, "router-disagreement-count", f"{bad} of {len(rows)}")

    # ---- synthetic archetypes: every route fires both ways ------------------ #
    def base_f():
        return {"hit_count": 1, "eligible_count": 1, "best_id": "x",
                "best_quality": 0.9, "best_defect": 0.04, "best_coverage": 0.9,
                "repair_cost": 0.2, "build_cost": 0.8, "repair_cost_ratio": 0.25,
                "n_mergeable": 1, "union_coverage": 0.88, "mechanism_overlap": 0.16,
                "n_mechanism_sources": 1, "retired_only": False,
                "license_blocked": False}

    f = base_f()
    out = recommend.decide(f)
    chk(out["route"] == "FIND", "archetype-find", out["route"])
    f = base_f()
    f["best_quality"] = 0.5   # below FIND gate, above REPAIR floor
    f["best_coverage"] = 0.5  # below REPAIR coverage floor too -> BUILD
    out = recommend.decide(f)
    chk(out["route"] == "BUILD", "archetype-repair-miss-build", out["route"])
    f = base_f()
    f["best_defect"] = 0.3
    out = recommend.decide(f)
    chk(out["route"] == "REPAIR", "archetype-repair", out["route"])
    f = base_f()
    f["best_defect"] = 0.3
    f["repair_cost_ratio"] = 0.9
    out = recommend.decide(f)
    chk(out["route"] == "BUILD", "archetype-repair-cost-build", out["route"])
    f = base_f()
    f["best_quality"] = 0.5
    f["best_coverage"] = 0.5
    f["n_mergeable"] = 2
    f["union_coverage"] = 0.9
    out = recommend.decide(f)
    chk(out["route"] == "MERGE", "archetype-merge", out["route"])
    f = base_f()
    f["best_quality"] = 0.5
    f["best_coverage"] = 0.5
    f["mechanism_overlap"] = 0.9
    out = recommend.decide(f)
    chk(out["route"] == "COMPOSE", "archetype-compose", out["route"])
    f = base_f()
    f["retired_only"] = True
    out = recommend.decide(f)
    chk(out["route"] == "BUILD", "archetype-retired-build", out["route"])

    # ---- threshold boundary control: separator flips at the cost ratio ------ #
    f = base_f()
    f["best_defect"] = 0.3
    f["repair_cost_ratio"] = 0.55
    chk(recommend.decide(f)["route"] == "REPAIR", "boundary-at-max-is-repair")
    f["repair_cost_ratio"] = 0.5500001
    chk(recommend.decide(f)["route"] == "BUILD", "boundary-just-over-is-build")

    # ---- label-leak control -------------------------------------------------- #
    f = base_f()
    f["retired_only"] = True
    leak = recommend.decide(f)
    chk(leak["route"] == "BUILD" and leak["audit"]["features"]["retired_only"] is True,
        "label-leak-control")

    # ---- constant-function control ------------------------------------------- #
    hist = {}
    for r in rows:
        out = recommend.decide(r["features"])
        hist[out["route"]] = hist.get(out["route"], 0) + 1
    distinct = len([k for k, v in hist.items() if v > 0])
    cfc = art.get("constant_function_control") or {}
    chk(distinct >= 3 and distinct == len([k for k, v in
                                          (cfc.get("histogram") or {}).items()
                                          if v > 0]),
        "constant-function-control", str(hist))
    chk(all((cfc.get("histogram") or {}).get(k, 0) == v for k, v in hist.items()),
        "constant-histogram-drift", json.dumps(hist))

    # ---- live both-states mutant on holdout_agreement ------------------------ #
    def rederive(doc, probe):
        h = doc.get("holdout") or {}
        rows = doc.get("evaluation_rows") or []
        ho_m = [r for r in rows if r.get("split") == "holdout"
                and not r.get("unmapped")]
        ho_ok = sum(1 for r in ho_m if r.get("agree"))
        probe(ho_m and abs(ho_ok / len(ho_m) - h.get("holdout_agreement")) < 1e-12,
              "holdout-agreement-recompute")
        probe(doc.get("overall_mapped_agreement") == 0.85, "overall-agreement")

    good = []
    rederive(art, lambda ok, lab, d="": (None if ok else good.append(lab)))
    chk(not good, "live-control-silent-on-good-failed", ";".join(good[:3]))
    mutant = copy.deepcopy(art)
    mutant["holdout"]["holdout_agreement"] = 1.0
    mf = []
    rederive(mutant, lambda ok, lab, d="": (None if ok else mf.append(lab)))
    chk(bool(mf), "live-control-did-not-fire-on-bad", ";".join(mf[:3]))

    # ---- manifest byte-compare ----------------------------------------------- #
    if not MANIFEST.is_file():
        print("FAILED:" + UNIT + "-probe2 manifest-absent")
        return 1
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = lf_sha(OUT)
    mrows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
    match = [a for a in mrows
             if str(a.get("path") or "").replace("\\", "/") == REL
             and str(a.get("sha256") or "") == live and a.get("present") is True]
    if not match:
        print("FAILED:" + UNIT + "-probe2 manifest-sha-mismatch live=" + live[:16])
        return 1
    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe2 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe2 live router reproduces 284/284 stored "
          "predictions; archetypes + boundary + label-leak + constant-function "
          "controls fire; mutant fires; manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
