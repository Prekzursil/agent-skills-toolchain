#!/usr/bin/env python3
"""Probe 1: recomputed closure counts + both-states unresolved-ref gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{G.UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    art = G.REPO / G.OUT_REL
    if not art.is_file() or art.stat().st_size <= 0:
        return fail("artifact missing")
    text = art.read_text(encoding="utf-8")
    if G.SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != G.UNIT:
        return fail("unit_id mismatch")
    if doc.get("not_legal_advice") is not True:
        return fail("not_legal_advice missing")

    art_graph = {"nodes": doc["nodes"], "edges": doc["edges"]}
    live = G.build_graph()
    live_ok, live_problems = G.closure_ok(live)
    if not live_ok:
        return fail(f"live closure {live_problems}")
    art_ok, art_problems = G.closure_ok(art_graph)
    if not art_ok:
        return fail(f"artifact closure {art_problems}")

    live_counts = G.recompute_counts(live)
    art_counts = G.recompute_counts(art_graph)
    stored = doc.get("counts") or {}
    for key in (
        "provenance_edges_unresolved",
        "provenance_resolution_rate",
        "blueprints",
        "non_owner_classified_with_fetched_licence_anchor",
        "unclassified_nodes",
    ):
        if stored.get(key) != art_counts.get(key) or art_counts.get(key) != live_counts.get(key):
            return fail(f"count drift {key} stored={stored.get(key)} art={art_counts.get(key)} live={live_counts.get(key)}")

    if art_counts["provenance_edges_unresolved"] != 0:
        return fail("unresolved provenance edges")
    if art_counts["provenance_resolution_rate"] != 1.0:
        return fail("resolution rate != 1.0")
    if G.classified_non_owner_missing_anchor(art_graph):
        return fail("classified non-owner missing fetched-licence anchor")
    if G.defaulted_unfetched(art_graph):
        return fail("unfetched node defaulted")
    listed = {r.get("id") for r in (doc.get("unclassified_nodes") or [])}
    live_listed = {r["id"] for r in G.unclassified_listed(art_graph)}
    if listed != live_listed or not listed:
        return fail("unclassified list mismatch or empty")

    drift = G.live_fetched_sha_matches(art_graph)
    if drift:
        return fail(f"fetched sha256 drift {drift}")

    planted = G.mutate_unresolved_ref(art_graph)
    plant_ok, plant_problems = G.closure_ok(planted)
    plant_counts = G.recompute_counts(planted)
    if plant_ok:
        return fail("unresolved-ref mutant stayed green")
    if plant_counts["provenance_edges_unresolved"] < 1:
        return fail("unresolved-ref mutant did not raise unresolved count")
    if plant_counts["provenance_resolution_rate"] >= 1.0:
        return fail("unresolved-ref mutant kept rate 1.0")
    if not any(p.startswith("unresolved-provenance:") for p in plant_problems):
        return fail(f"unresolved-ref fingerprint missing {plant_problems}")

    defaulted = G.mutate_default_unfetched_to_mit(art_graph)
    def_ok, def_problems = G.closure_ok(defaulted)
    if def_ok or not any(p.startswith("defaulted-unfetched:") for p in def_problems):
        return fail(f"default-to-MIT mutant silent {def_problems}")

    honesty = doc.get("honesty_block") or {}
    if not honesty.get("now_measured") or not honesty.get("remains_rule_based"):
        return fail("honesty block incomplete")

    out = {
        "probe": "probe1-closure-counts",
        "unit_id": G.UNIT,
        "pass": True,
        "provenance_edges_unresolved": art_counts["provenance_edges_unresolved"],
        "provenance_resolution_rate": art_counts["provenance_resolution_rate"],
        "non_owner_classified_with_fetched_licence_anchor": art_counts[
            "non_owner_classified_with_fetched_licence_anchor"
        ],
        "unclassified_listed": sorted(listed),
        "unresolved_ref_mutant_red": True,
        "default_to_mit_mutant_red": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "unresolved="
        f"{art_counts['provenance_edges_unresolved']} "
        f"rate={art_counts['provenance_resolution_rate']} "
        f"unclassified={len(listed)} "
        "mutant_red=True"
    )
    print("SUCCESS:WFA-0079-probe1 closure counts and both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
