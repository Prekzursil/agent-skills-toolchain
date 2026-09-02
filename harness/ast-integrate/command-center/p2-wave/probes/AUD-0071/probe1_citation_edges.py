#!/usr/bin/env python3
"""Probe 1: build support edges from explicit citation.

A lexical mention of another claim id in the body is not an edge.
Dangling citations are recorded, not silently dropped.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from corpus import load_corpus  # noqa: E402
from graph import build, citation_edges  # noqa: E402

ART = REPO / "command-center/audit/AUD-0071-support-edge-graph.json"
SENTINEL = (
    "SUCCESS:AUD-0071 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0071-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")

    corpus = load_corpus()
    live_edges, live_unresolved = citation_edges(corpus["claims"])
    graph = build(corpus["claims"])
    art_edges = doc.get("support_edges") or []
    live_pairs = {(e["from"], e["to"]) for e in live_edges}
    art_pairs = {(e["from"], e["to"]) for e in art_edges if isinstance(e, dict)}
    if live_pairs != art_pairs:
        extra = sorted(art_pairs - live_pairs)[:8]
        missing = sorted(live_pairs - art_pairs)[:8]
        return fail(f"artifact edges != recomputed extra={extra} missing={missing}")

    five_supporters = {
        "CTL-FIVE-ONE-R1",
        "CTL-FIVE-ONE-R2",
        "CTL-FIVE-ONE-R3",
        "CTL-FIVE-ONE-R4",
        "CTL-FIVE-ONE-R5",
    }
    got = {frm for frm, to in live_pairs if to == "CTL-FIVE-ONE-TARGET"}
    if got != five_supporters:
        return fail(f"five-from-one edges {sorted(got)}")

    if ("CTL-PROSE-A", "CTL-PROSE-B") in live_pairs or (
        "CTL-PROSE-B",
        "CTL-PROSE-A",
    ) in live_pairs:
        return fail("prose mention became a support edge")

    incoming_nocite = [e for e in live_edges if e["to"] == "CTL-NOCITE"]
    if incoming_nocite:
        return fail("CTL-NOCITE has incoming support")

    dangling = [u for u in live_unresolved if u["to"] == "CTL-DOES-NOT-EXIST"]
    if not dangling:
        return fail("dangling citation dropped")
    art_unres = doc.get("unresolved_citations") or []
    if not any(isinstance(u, dict) and u.get("to") == "CTL-DOES-NOT-EXIST" for u in art_unres):
        return fail("artifact omitted dangling citation")

    print(
        json.dumps(
            {
                "edge_count": len(live_edges),
                "unresolved": len(live_unresolved),
                "five_one_supporters": sorted(got),
                "prose_pair_is_edge": False,
                "artifact_matches_recompute": True,
                "claim_count": graph["claim_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    print("SUCCESS:AUD-0071-probe1 citation-support-edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
