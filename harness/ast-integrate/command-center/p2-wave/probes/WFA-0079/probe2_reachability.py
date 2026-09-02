#!/usr/bin/env python3
"""Probe 2: independent reachability walk from each blueprint to a licence class."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{G.UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    art = G.REPO / G.OUT_REL
    if not art.is_file():
        return fail("artifact missing")
    doc = json.loads(art.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    graph = {"nodes": doc["nodes"], "edges": doc["edges"]}

    honesty = doc.get("honesty_block") or {}
    measured = honesty.get("now_measured") or []
    remains = honesty.get("remains_rule_based") or []
    if len(measured) < 3 or len(remains) < 2:
        return fail("honesty block too thin")
    if not any("reachability" in str(x).lower() or "walk" in str(x).lower() for x in measured):
        return fail("honesty block does not name the walk")
    if not any("rule" in str(x).lower() or "UNCLASSIFIED" in str(x) for x in remains):
        return fail("honesty block does not name residual rule-based work")

    missing = G.blueprints_missing_licence_class(graph)
    if missing:
        return fail(f"blueprint walk miss {missing}")
    field_bad = G.nodes_with_licence_field_but_unreachable_class(graph)
    if field_bad:
        return fail(f"licence field without walk {field_bad}")

    walks = {}
    classes = G.licence_class_ids(graph)
    for bid in G.blueprint_ids(graph):
        seen = G.reachable(graph, bid)
        hit = sorted(seen & classes)
        walks[bid] = hit
        if not hit:
            return fail(f"no licence-class reachable from {bid}")

    dropped = G.mutate_drop_licensed_as(graph, "bp.benchmark-generation")
    drop_missing = G.blueprints_missing_licence_class(dropped)
    drop_field = G.nodes_with_licence_field_but_unreachable_class(dropped)
    if "bp.benchmark-generation" not in drop_missing and "bp.benchmark-generation" not in drop_field:
        return fail("drop-licensed-as walk stayed green")
    healthy_ok, _ = G.closure_ok(graph)
    if not healthy_ok:
        return fail("healthy graph not ok")
    drop_ok, _ = G.closure_ok(dropped)
    if drop_ok:
        return fail("drop-licensed-as closure stayed green")

    register = doc.get("license_risk_register") or []
    ids = {r.get("id") for r in register if isinstance(r, dict)}
    for needed in (
        "risk:MIT-notice",
        "risk:BMAD-trademark-rider",
        "risk:CC-BY-4.0-attribution",
        "risk:UNCLASSIFIED-no-permissive-default",
    ):
        if needed not in ids:
            return fail(f"risk register missing {needed}")
    rider = next(r for r in register if r.get("id") == "risk:BMAD-trademark-rider")
    if "BMad Code, LLC" not in str(rider.get("obligation") or ""):
        return fail("trademark rider not transcribed")
    if rider.get("verbatim_from_file") is not True:
        return fail("rider not marked verbatim")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "WFA-0079-UNRESOLVED-REF-MUTANT",
        "WFA-0079-HONESTY-BLOCK",
        "WFA-0079-UNCLASSIFIED-NO-DEFAULT",
    ):
        if tests.get(tid, {}).get("result") != "PASS":
            return fail(f"artifact test {tid} not PASS")

    out = {
        "probe": "probe2-reachability",
        "unit_id": G.UNIT,
        "pass": True,
        "blueprints": walks,
        "drop_licensed_as_caught": True,
        "honesty_measured": len(measured),
        "honesty_rule_based": len(remains),
        "risk_register_rows": len(register),
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"blueprints={len(walks)} drop_caught=True "
        f"honesty={len(measured)}/{len(remains)} risks={len(register)}"
    )
    print("SUCCESS:WFA-0079-probe2 reachability walk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
