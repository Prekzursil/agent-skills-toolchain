#!/usr/bin/env python3
"""CNF-0169 named probe 1 (wave-2 reconstruction): ten pairwise set differences.

Re-derives the five registry id sets live under the receipt's set-membership
rule ("only explicit registry ids are members; receipts keyed by filename
stem"), emits all C(5,2)=10 pairwise differences with counts and sample ids,
and verifies the receipt's recorded pairwise table is structurally coherent
(ten unique pairs, symmetric-count arithmetic, empty-diff digest rule).
Live counts are RECORDED, never asserted against the dated snapshot.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "command-center"
ART = CC / "receipts" / "CNF-0169.json"
RAW_OUT = HERE / "probe1-live.raw.txt"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def five_sets():
    claims = load_json(CC / "CLAIM-REGISTRY.json")
    claims_ids = {str(c["id"]) for c in claims.get("claims", []) if isinstance(c, dict) and c.get("id")}
    tests = load_json(CC / "TEST-REGISTRY.json")
    tests_ids = {str(t["id"]) for t in tests.get("invariants", []) if isinstance(t, dict) and t.get("id")}
    artifacts = load_json(CC / "ARTIFACT-MANIFEST.json")
    art_ids = {str(a["id"]) for a in artifacts.get("artifacts", []) if isinstance(a, dict) and a.get("id")}
    catalog = load_json(CC / "WORK-UNIT-CATALOG.json")
    cat_ids = {str(u["id"]) for u in catalog.get("work_units", []) if isinstance(u, dict) and u.get("id")}
    cat_ids |= {str(i["id"]) for i in catalog.get("items", []) if isinstance(i, dict) and i.get("id")}
    rec_ids = {p.stem for p in (CC / "receipts").glob("*.json")}
    return {
        "claims": claims_ids,
        "tests": tests_ids,
        "artifacts": art_ids,
        "catalog": cat_ids,
        "receipts": rec_ids,
    }


def differ(left, right):
    lm = sorted(left - right)
    rm = sorted(right - left)
    return {
        "left_minus_right": {
            "count": len(lm),
            "sample_ids": lm[:5],
            "digest": hashlib.sha256("\n".join(lm).encode("utf-8")).hexdigest() if lm else EMPTY_SHA,
        },
        "right_minus_left": {
            "count": len(rm),
            "sample_ids": rm[:5],
            "digest": hashlib.sha256("\n".join(rm).encode("utf-8")).hexdigest() if rm else EMPTY_SHA,
        },
        "symmetric_count": len(lm) + len(rm),
    }


def main() -> int:
    lines = []

    def emit(s=""):
        lines.append(s)

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0169-probe1 receipt missing")
        return 1
    txt = ART.read_text(encoding="utf-8")
    doc = load_json(ART)
    if "SUCCESS:CNF-0169" not in txt:
        print("FAILED:CNF-0169-probe1 sentinel absent")
        return 1
    if str(doc.get("state", "")).upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0169-probe1 self-declared " + str(doc.get("state")))
        return 1

    sets = five_sets()
    names = ["claims", "tests", "artifacts", "catalog", "receipts"]  # canonical receipt order
    assert sorted(sets) == sorted(names), sorted(sets)
    emit("CNF-0169 PROBE1 LIVE RERUN: five registry id sets, membership per receipt rule")
    for n in names:
        emit("set " + n + ": " + str(len(sets[n])) + " ids")

    pairs = {}
    for a, b in itertools.combinations(names, 2):
        key = a + "|" + b
        pairs[key] = differ(sets[a], sets[b])
        emit(
            "pair " + key
            + ": L-R=" + str(pairs[key]["left_minus_right"]["count"])
            + " R-L=" + str(pairs[key]["right_minus_left"]["count"])
            + " sym=" + str(pairs[key]["symmetric_count"])
        )
    if len(pairs) != 10:
        print("FAILED:CNF-0169-probe1 pairwise rows " + str(len(pairs)) + " != 10")
        return 1

    rec_rows = doc.get("pairwise_differences") or []
    rec_pairs = [str(r.get("pair")) for r in rec_rows if isinstance(r, dict)]
    # unordered pair-set comparison (receipt used the canonical order, we re-derive it)
    if {frozenset(x.split("|")) for x in rec_pairs} != {frozenset(x.split("|")) for x in pairs}:
        print("FAILED:CNF-0169-probe1 receipt pairwise pairs do not cover C(5,2)")
        return 1
    for r in rec_rows:
        lm = r.get("left_minus_right") or {}
        rm = r.get("right_minus_left") or {}
        if int(r.get("symmetric_count", -1)) != int(lm.get("count", -1)) + int(rm.get("count", -1)):
            print("FAILED:CNF-0169-probe1 symmetric arithmetic bad on " + str(r.get("pair")))
            return 1
        if int(lm.get("count", 1)) == 0 and lm.get("digest") != EMPTY_SHA:
            print("FAILED:CNF-0169-probe1 empty-diff digest rule violated on " + str(r.get("pair")) + " left")
            return 1
        if int(rm.get("count", 1)) == 0 and rm.get("digest") != EMPTY_SHA:
            print("FAILED:CNF-0169-probe1 empty-diff digest rule violated on " + str(r.get("pair")) + " right")
            return 1

    inter = set.intersection(*[sets[n] for n in names])
    agree = all(sets[n] == sets[names[0]] for n in names)
    if agree:
        print("FAILED:CNF-0169-probe1 live five registries agree; recorded CONFIRMED disagreement stale")
        return 1

    live_sizes = {n: len(sets[n]) for n in names}
    snap = doc.get("live_set_sizes") or {}
    drift = {
        n: {"snapshot": snap.get(n), "live": live_sizes[n]}
        for n in names
        if snap.get(n) != live_sizes[n]
    }
    emit("intersection_all_five=" + str(len(inter)) + " five_way_agree=" + str(agree))
    emit("snapshot drift (snapshot dated 2026-08-19; recorded, not failed): " + json.dumps(drift, sort_keys=True))
    RAW_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    report = {
        "probe": "probe1-live-ten-pairwise",
        "unit_id": "CNF-0169",
        "live_set_sizes": live_sizes,
        "intersection_all_five": len(inter),
        "five_way_agree": agree,
        "pairwise_rows_live": len(pairs),
        "receipt_pairwise_rows_coherent": True,
        "snapshot_drift_recorded": drift,
        "computed_not_asserted": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("SUCCESS:CNF-0169-probe1 ten pairwise set differences emitted live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
