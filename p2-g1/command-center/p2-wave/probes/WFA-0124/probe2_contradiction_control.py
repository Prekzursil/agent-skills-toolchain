#!/usr/bin/env python3
"""WFA-0124 probe2 -- contradiction + demotion controls (mechanically different).

Re-runs the detector battery on the re-materialized known-broken fixture
library (7 blueprints, 3 executable, 1 flagship) via measure.py's classify
path, asserts every recorded detector_control boolean, runs the live both-states
control on the ARTIFACT (totals recompute must fire on a mutated headline count
and stay silent on the intact artifact), and byte-compares the per-unit
manifest. Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/wfa/WFA-0124-blueprint-executability-gap.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0124"
REL = "command-center/wfa/WFA-0124-blueprint-executability-gap.json"

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    import importlib.util
    spec = importlib.util.spec_from_file_location("wfa124_measure", HERE / "measure.py")
    mm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mm)

    try:
        art = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 artifact-unreadable:" + type(exc).__name__)
        return 1

    # ---- fixture detector battery ------------------------------------------ #
    lib = mm.measure_library(sorted((HERE / "fixtures" / "library").glob("*.json")))
    dc = art.get("detector_controls") or {}
    chk(lib["totals"]["live_blueprint_rows"] == dc.get("fixture_catalog_claim") == 7,
        "fixture-row-count", str(lib["totals"]["live_blueprint_rows"]))
    chk(lib["totals"]["measured_executable"] == dc.get("fixture_measured_executable_count") == 3,
        "fixture-executable-count", str(lib["totals"]["measured_executable"]))
    flag_ids = [r["id"] for r in lib["rows"] if r["flagship_identified"]]
    chk(flag_ids == (dc.get("fixture_flagship_identified") or []) == ["bp.ok.flagship"],
        "fixture-flagship-ids", str(flag_ids))
    chk(dc.get("native_contradiction_fired") is True
        and any(c["kind"] == "declared-native-but-unloadable"
                and c["blueprint_id"] == "bp.contradiction.native-unloadable"
                for c in lib["contradictions"]),
        "native-contradiction-not-fired")
    chk(dc.get("flagship_claimed_demoted") is True
        and lib["declared_flagship_count"] == dc.get("mutant_declared_flagship_count") == 2
        and lib["totals"]["flagship_identified"] == dc.get("identified_flagship_count") == 1,
        "flagship-demotion-numbers",
        json.dumps([lib["declared_flagship_count"], lib["totals"]["flagship_identified"]]))
    chk(dc.get("load_error_classified") is True
        and any(r["classification"] == "load-error"
                for r in lib["rows"]),
        "load-error-classified")
    chk(dc.get("no_artifact_classified_failure") is True
        and all(r["classification"] in ("executable", "failure", "load-error")
                for r in lib["rows"]),
        "classification-set-drift")
    chk(dc.get("discovery_consistent") is True
        and (lambda r: r["classification"] != "executable"
             and r["declared_discovery_only"] is True)
        (next(r for r in lib["rows"] if r["id"] == "bp.discovery-only")),
        "discovery-only-row-consistency")
    chk(dc.get("remaining_work_concrete") is True
        and all(mm.is_concrete(r["remaining_work"])
                for r in lib["rows"] if r["classification"] != "executable"),
        "remaining-work-concrete-check")
    vague = [{"task_id": "X", "action": "make executable",
              "acceptance": "it works", "owner_lane": "x"}]
    chk(dc.get("vague_mutant_rejected") is True
        and mm.is_concrete(vague) is False, "vague-mutant-not-rejected")

    # ---- live both-states control on the ARTIFACT -------------------------- #
    def totals_recompute(d):
        rows = d.get("rows") or []
        return {
            "live_blueprint_rows": len(rows),
            "ir_load_ok": sum(1 for r in rows if r["ir_load"].get("ok")),
            "smoke_ok": sum(1 for r in rows if r["smoke"].get("ok")),
            "measured_executable": sum(1 for r in rows
                                       if r.get("classification") == "executable"),
            "flagship_identified": sum(1 for r in rows if r.get("flagship_identified")),
            "contradictions": len(d.get("contradictions") or []),
        }

    def agree(doc, probe):
        t = totals_recompute(doc)
        pub = doc.get("totals") or {}
        mism = {k: (t[k], pub.get(k)) for k in t if pub.get(k) != t[k]}
        probe(not mism, "totals-recompute-mismatch", json.dumps(mism)[:400])
        probe(doc.get("measured_executable_count") == t["measured_executable"],
              "measured-count-mismatch")

    good = []
    agree(art, lambda ok, l, d="": (None if ok else good.append(l)))
    chk(not good, "live-control-silent-on-good-failed", ";".join(good[:3]))
    mutant = copy.deepcopy(art)
    mutant["measured_executable_count"] = 96
    mutant["totals"]["measured_executable"] = 96
    mf = []
    agree(mutant, lambda ok, l, d="": (None if ok else mf.append(l)))
    chk(bool(mf), "live-control-did-not-fire-on-bad", ";".join(mf[:3]))

    # ---- manifest byte-compare --------------------------------------------- #
    if not MANIFEST.is_file():
        print("FAILED:" + UNIT + "-probe2 manifest-absent")
        return 1
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    live = lf_sha(OUT)
    rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
    match = [a for a in rows
             if str(a.get("path") or "").replace("\\", "/") == REL
             and str(a.get("sha256") or "") == live and a.get("present") is True]
    if not match:
        print("FAILED:" + UNIT + "-probe2 manifest-sha-mismatch live=" + live[:16])
        return 1
    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe2 " + f)
        return 1
    print("SUCCESS:" + UNIT + "-probe2 detector battery reproduces recorded controls "
          "(7 fixtures, 3 executable, 1 flagship, native contradiction + demotion "
          "+ vague-mutant rejection); artifact totals recompute; mutant fires; "
          "manifest byte-compare OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
