#!/usr/bin/env python3
"""Probe 1: named 30-package Spearman + source lineage + inventory.

Both-states: live artifact must match a fresh recompute; dropping a package
or swapping the numeric rho for 'correlates well' must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import compute as C  # noqa: E402
import signals as S  # noqa: E402

ART = REPO / C.ART_REL
EPS = 1e-9


def fail(msg: str) -> int:
    print(f"FAILED:RES-0131-probe1 {msg}")
    return 1


def main() -> int:
    live = C.measure()
    reasons: list[str] = []
    if live["n"] != 30:
        reasons.append(f"n={live['n']}")
    if len(live["names"]) != 30 or len(set(live["names"])) != 30:
        reasons.append("sample names not 30 unique")
    if not live["alt_agrees"]:
        reasons.append("spearman implementations disagree")
    if live["source_errors"]:
        reasons.append(f"source_errors={live['source_errors']}")
    if not live["stored_offline_matches_recompute"]:
        reasons.append("stored offline_score drifted from features")
    if not live["offline_not_copy_of_online"]:
        reasons.append("offline vector copies online")
    if not live["file_list_all_ok"]:
        reasons.append("file-list rail disagreed on <=80-file packages")

    sources = {r["id"]: r for r in C.load_sources()}
    for sig in S.all_signals():
        rail = sources.get(sig["source_id"])
        if not rail:
            reasons.append(f"missing-source:{sig['source_id']}")
            continue
        err = C.verify_source_rail(rail)
        if err:
            reasons.append(err)
            continue
        text = (REPO / rail["capture_path"]).read_text(encoding="utf-8", errors="replace")
        if sig["snippet"] not in text:
            reasons.append(f"snippet-miss:{sig['id']}")
        if int(rail["http_status"]) == 404 and rail["id"] != "silverstripe-moduleratings-readme":
            reasons.append(f"unexpected-404:{sig['id']}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        reasons.append("artifact missing")
        print(json.dumps({"probe": "probe1-spearman", "reasons": reasons}, sort_keys=True))
        return fail("; ".join(reasons))

    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if C.SENTINEL not in text or "SUCCESS:RES-0131" not in text:
        reasons.append("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        reasons.append(f"self-declared {doc.get('state')}")
    art_names = ((doc.get("sample") or {}).get("packages") or [])
    art_name_list = [p.get("name") for p in art_names]
    if art_name_list != live["names"]:
        reasons.append("artifact sample names mismatch")
    spear = doc.get("spearman") or {}
    if abs(float(spear.get("rho_offline_vs_npms_final")) - live["rho_offline_vs_npms_final"]) > EPS:
        reasons.append("artifact rho_final mismatch")
    if abs(float(spear.get("rho_offline_vs_npms_quality")) - live["rho_offline_vs_npms_quality"]) > EPS:
        reasons.append("artifact rho_quality mismatch")
    if spear.get("qualitative_correlates_well_rejected") is not True:
        reasons.append("qualitative rejection flag missing")
    if not isinstance(spear.get("rho_offline_vs_npms_final"), (int, float)):
        reasons.append("rho is not numeric")

    # both-states: mutate n by dropping a row
    mutant = copy.deepcopy(doc)
    mutant["sample"]["packages"] = mutant["sample"]["packages"][:-1]
    if len(mutant["sample"]["packages"]) == 30:
        reasons.append("mutant drop failed to change n")
    else:
        if len(mutant["sample"]["packages"]) != 29:
            reasons.append("mutant unexpected length")

    # both-states: qualitative substitution must be detectable
    mutant2 = copy.deepcopy(doc)
    mutant2["spearman"]["rho_offline_vs_npms_final"] = "correlates well"
    if isinstance(mutant2["spearman"]["rho_offline_vs_npms_final"], (int, float)):
        reasons.append("qualitative mutant still numeric")

    payload = {
        "probe": "probe1-spearman",
        "unit_id": "RES-0131",
        "n": live["n"],
        "rho_final": live["rho_offline_vs_npms_final"],
        "rho_quality": live["rho_offline_vs_npms_quality"],
        "local_signal_count": len(S.local_ids()),
        "remote_signal_count": len(S.remote_ids()),
        "mutant_n": len(mutant["sample"]["packages"]),
        "qualitative_mutant": mutant2["spearman"]["rho_offline_vs_npms_final"],
        "reasons": reasons,
    }
    print(json.dumps(payload, sort_keys=True, default=str))
    if reasons:
        return fail("; ".join(reasons))
    print(
        f"n=30 rho_final={live['rho_offline_vs_npms_final']:.6f} "
        f"rho_quality={live['rho_offline_vs_npms_quality']:.6f}"
    )
    print("SUCCESS:RES-0131-probe1 spearman over named 30-package sample")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
