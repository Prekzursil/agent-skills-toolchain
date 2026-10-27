#!/usr/bin/env python3
"""Probe 2: independent fusion attempts + graph set-algebra (no checker import)."""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fusion as F  # noqa: E402

UNIT = "WFA-0107"
OUT = "command-center/wfa/WFA-0107-fusion-precondition-checker.json"
SENTINEL = "SUCCESS:WFA-0107"
FIXTURES = HERE / "fixtures"

# Deliberate: this file must not import checker.
if "checker" in sys.modules:
    print(f"FAILED:{UNIT}-probe2 checker already imported")
    raise SystemExit(1)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def edge(a: str, b: str) -> frozenset:
    return frozenset((a, b))


def shadow_without_licence(left: dict, right: dict, compat, conflicts) -> str:
    """Mutant: skip the licence matrix. Must NOT match the live checker on prop pairs."""
    if edge(left["id"], right["id"]) not in compat:
        return "ILLEGAL"
    for ma in left["mechanisms"]:
        for mb in right["mechanisms"]:
            if ma != mb and edge(ma, mb) in conflicts:
                return "ILLEGAL"
    return "LEGAL"


def main() -> int:
    if "checker" in sys.modules:
        return fail("imported checker")
    art_path = REPO / OUT
    if not art_path.is_file():
        return fail("artifact missing")
    text = art_path.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    bps_doc = load_json("blueprints.json")
    compat_doc = load_json("compat_relation.json")
    conf_doc = load_json("mechanism_conflicts.json")
    lic_doc = load_json("licence_matrix.json")
    bps = {b["id"]: b for b in bps_doc["blueprints"]}
    compat = {edge(e["source"], e["target"]) for e in compat_doc["edges"]}
    conflicts = {edge(e["left"], e["right"]) for e in conf_doc["edges"]}
    licence = {
        edge(c["left"], c["right"]): c["verdict"] for c in lic_doc["cells"]
    }

    fusion_mutex = F.MUTEX
    if fusion_mutex != conflicts:
        return fail(f"fusion MUTEX drifted from conflict graph {fusion_mutex} vs {conflicts}")

    # Fusion attempts vs every artifact verdict (does not call checker.check).
    over = []
    under = []
    fusion_bps = F.load_blueprints()
    for row in doc["verdicts"]:
        att = F.attempt(row["left"], row["right"], row["operator"], fusion_bps)
        rev = F.attempt(row["right"], row["left"], row["operator"], fusion_bps)
        if row["verdict"] == "LEGAL":
            if not att["ok"] or not rev["ok"]:
                under.append(
                    {
                        "cell": row,
                        "fwd": att["defects"],
                        "rev": rev["defects"],
                    }
                )
        else:
            if att["ok"]:
                over.append({"cell": row, "defects": att["defects"]})
    if under:
        return fail(f"under-refusal n={len(under)} sample={under[0]}")
    if over:
        return fail(f"over-refusal n={len(over)} sample={over[0]}")

    # Licence-omit mutant: structural+mechanism only would allow a-prop.
    a = bps["wf-review-a"]
    prop = bps["wf-review-prop"]
    if edge("wf-review-a", "wf-review-prop") not in compat:
        return fail("a-prop missing compat in graph")
    if licence[edge(a["licence"], prop["licence"])] != "FORBID":
        return fail("a-prop licence cell not FORBID")
    shadow = shadow_without_licence(a, prop, compat, conflicts)
    if shadow != "LEGAL":
        return fail(f"licence-omit mutant did not fire (shadow={shadow})")
    live = [
        r
        for r in doc["verdicts"]
        if {r["left"], r["right"]} == {"wf-review-a", "wf-review-prop"}
        and r["operator"] == "union"
    ]
    if len(live) != 1 or live[0]["verdict"] != "ILLEGAL":
        return fail("live checker missed licence pair")
    if "licence" not in (live[0].get("blocking_edge") or ""):
        return fail("live licence pair not named as licence edge")
    if F.attempt("wf-review-a", "wf-review-prop", "union", fusion_bps)["ok"]:
        return fail("fusion attempt did not catch licence pair")

    # Set-algebra recount of compat/conflict/licence for union-only (graph
    # gates, ignoring operator extras): must match artifact union verdicts
    # on those three gates.
    ids = sorted(bps)
    union_mismatch = []
    for x, y in combinations(ids, 2):
        expected = "LEGAL"
        reason_kind = None
        if edge(x, y) not in compat:
            expected = "ILLEGAL"
            reason_kind = "compat"
        else:
            la, lb = bps[x]["licence"], bps[y]["licence"]
            if licence.get(edge(la, lb), "FORBID") != "ALLOW":
                expected = "ILLEGAL"
                reason_kind = "licence"
            else:
                hit = False
                for ma in bps[x]["mechanisms"]:
                    for mb in bps[y]["mechanisms"]:
                        if ma != mb and edge(ma, mb) in conflicts:
                            hit = True
                if hit:
                    expected = "ILLEGAL"
                    reason_kind = "mechanism-conflict"
        art = next(
            r
            for r in doc["verdicts"]
            if {r["left"], r["right"]} == {x, y} and r["operator"] == "union"
        )
        if expected == "ILLEGAL" and art["verdict"] != "ILLEGAL":
            union_mismatch.append((x, y, reason_kind, art["verdict"]))
        if expected == "LEGAL" and art["verdict"] == "ILLEGAL":
            # union has no extra operator gate, so this is a real mismatch
            union_mismatch.append((x, y, "union-should-be-legal", art["blocking_edge"]))
    if union_mismatch:
        return fail(f"union set-algebra mismatch {union_mismatch[:3]}")

    print(
        json.dumps(
            {
                "ok": True,
                "probe": "probe2-independent-attempts",
                "unit_id": UNIT,
                "imported_checker": "checker" in sys.modules,
                "fusion_cells": len(doc["verdicts"]),
                "licence_omit_mutant_detected": True,
                "mutex_matches_conflict_graph": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UNIT}-probe2 independent-fusion n={len(doc['verdicts'])} "
        "licence-omit-mutant-detected checker-not-imported"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
