#!/usr/bin/env python3
"""WFA-0123 probe2 -- independent content re-derivation (third code path).

Recomputes the three-way AND on the live registry (9 raw rows) and on the
planted both-states fixture (7 raw rows) with an inline implementation that
imports NEITHER qualify_a NOR qualify_b, verifies the shortfall is routed not
massaged (floor 160, shortfall published), checks the stopping-condition
statement, and byte-compares the per-unit manifest against the live artifact
(LF-normalized sha256, matching _measure_one_delivered.py). Fails closed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "command-center/wfa/WFA-0123-candidate-floor-proof.json"
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"
UNIT = "WFA-0123"
REL = "command-center/wfa/WFA-0123-candidate-floor-proof.json"
FLOOR = 160

fails = []


def chk(ok, label, detail=""):
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def inline_qualify(records, repo_root: Path):
    """probe2's own three-way AND: aliases-field alias link + exact-mechanism
    duplicate collapse + classification/provenance/SPDX-file AND. A third
    implementation written from the stopping-condition text, not an import."""
    excluded = {"alias": [], "duplicate": [], "trivial_fork": []}
    survivors = []
    for r in records:
        drop = False
        r_tokens = set(re.findall(r"[a-z0-9]+", (r.get("mechanism") or "").lower()))
        for s in survivors:
            if r.get("id") in (s.get("aliases") or []):
                excluded["alias"].append(r["id"])
                drop = True
                break
            s_tokens = set(re.findall(r"[a-z0-9]+", (s.get("mechanism") or "").lower()))
            if r_tokens and r_tokens <= s_tokens:
                excluded["duplicate"].append(r["id"])
                drop = True
                break
        if not drop:
            survivors.append(r)
    qualified = []
    for r in survivors:
        c = str(r.get("classification") or "")
        ok_class = bool(c) and c != "UNKNOWN-NEEDS-PROBE"
        pf = r.get("provenance_file")
        ok_prov = bool(pf) and (repo_root / pf).is_file()
        lf = r.get("licence_file")
        ok_lic = False
        if lf and (repo_root / lf).is_file():
            head = (repo_root / lf).read_text(encoding="utf-8", errors="replace")[:400]
            ok_lic = bool(re.search(r"SPDX-License-Identifier:\s*[A-Za-z0-9.-]+", head))
        if ok_class and ok_prov and ok_lic:
            qualified.append(r["id"])
    return {
        "raw_count": len(records),
        "excluded_counts": {k: len(v) for k, v in excluded.items()},
        "after_collapse": len(survivors),
        "qualified_count": len(qualified),
        "qualified_ids": qualified,
    }


def main() -> int:
    try:
        art = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception as exc:
        print("FAILED:" + UNIT + "-probe2 unreadable:" + type(exc).__name__)
        return 1

    reg = json.loads((REPO / "command-center/wfa/WFA-0078-candidate-registry-v2.json")
                     .read_text(encoding="utf-8"))
    live = inline_qualify(reg["records"], REPO)
    chk(live["raw_count"] == 9, "live-raw-count", str(live["raw_count"]))
    chk(live["qualified_count"] == 0, "live-qualified-count",
        json.dumps(live["qualified_ids"]))
    chk(live["after_collapse"] == 9, "live-after-collapse", str(live["after_collapse"]))
    chk(art.get("qualified_count") == 0 and art.get("raw_count") == 9,
        "artifact-live-numbers-drift")
    chk(art.get("floor") == FLOOR and art.get("floor_clears") is False,
        "floor-not-published-honestly")
    shortfall = art.get("shortfall")
    chk(shortfall == FLOOR - art.get("qualified_count", 0) == 160,
        "shortfall-arithmetic", str(shortfall))
    route = art.get("shortfall_route") or {}
    chk(bool(route.get("routed_to")) and "do_not" in route,
        "shortfall-not-routed")
    chk("Do not massage" in route.get("do_not", ""), "do-not-massage-missing")
    chk(str(art.get("stopping_condition_16", "")).startswith(
        "At least 160 workflow candidates"), "stopping-condition-text-drift")
    # gap block explains raw - qualified
    gap = art.get("gap") or {}
    chk(gap.get("raw_minus_qualified") ==
        art.get("raw_count", 0) - art.get("qualified_count", 0),
        "gap-arithmetic")

    fx = json.loads((HERE / "fixtures" / "planted_registry.json")
                    .read_text(encoding="utf-8"))
    planted = inline_qualify(fx["records"], REPO)
    chk(planted["raw_count"] == 7, "planted-raw-count")
    chk(planted["after_collapse"] == 5, "planted-after-collapse",
        str(planted["after_collapse"]))
    chk(planted["qualified_count"] == 2, "planted-qualified-count",
        json.dumps(planted["qualified_ids"]))
    bs = art.get("both_states") or {}
    chk(bs.get("planted_raw") == 7 and bs.get("planted_qualified") == 2,
        "both-states-recorded-numbers-drift")
    chk(bs.get("licence_string_is_not_fetched") is True,
        "licence-string-rule-drift")

    # live both-states control: mutation of the qualified count must fire
    def good_probe(ok, label, detail=""):
        if not ok:
            good_fails.append(label)

    def bad_probe(ok, label, detail=""):
        if not ok:
            mutant_fails.append(label)

    good_fails = []
    rederive_check(art, good_probe)
    chk(not good_fails, "live-control-silent-on-good-failed", ";".join(good_fails[:3]))
    mutant = copy.deepcopy(art)
    mutant["qualified_count"] = 160
    mutant["floor_clears"] = True
    mutant_fails = []
    rederive_check(mutant, bad_probe)
    chk(bool(mutant_fails), "live-control-did-not-fire-on-bad",
        ";".join(mutant_fails[:3]))

    if fails:
        for f in fails[:12]:
            print("FAILED:" + UNIT + "-probe2 " + f)
        return 1
    if MANIFEST.is_file():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live_sha = lf_sha(OUT)
        rows = [a for a in man.get("artifacts") or [] if a.get("unit_id") == UNIT]
        match = [a for a in rows
                 if str(a.get("path") or "").replace("\\", "/") == REL
                 and str(a.get("sha256") or "") == live_sha
                 and a.get("present") is True]
        if not match:
            print("FAILED:" + UNIT + "-probe2 manifest-sha-mismatch live=" + live_sha[:16])
            return 1
    else:
        print("FAILED:" + UNIT + "-probe2 manifest-absent")
        return 1
    print("SUCCESS:" + UNIT + "-probe2 inline three-way AND reproduces live 9->0 and "
          "planted 7->2; shortfall routed not massaged; live mutant control + manifest "
          "byte-compare OK")
    return 0


def rederive_check(art, probe):
    """Fast invariants that must hold on any honest copy of this artifact."""
    probe(art.get("qualified_count") == 0, "q-count-zero")
    probe(art.get("floor_clears") is False, "floor-clears-false")
    probe(art.get("shortfall") == 160, "shortfall-160")
    probe((art.get("gap") or {}).get("raw_minus_qualified")
          == art.get("raw_count", 0) - art.get("qualified_count", 0), "gap-math")
    probe((art.get("both_states") or {}).get("planted_qualified") == 2,
          "planted-2")
    probe(art.get("qualified_count", 1) < 160, "no-massage-to-floor")


if __name__ == "__main__":
    raise SystemExit(main())
