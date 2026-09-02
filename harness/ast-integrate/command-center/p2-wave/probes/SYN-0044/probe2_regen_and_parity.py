#!/usr/bin/env python3
"""Probe 2: graph-edit regeneration changes the diagram; generator does not write the gated file."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import generate as G  # noqa: E402
import schema_local as SL  # noqa: E402

ART = REPO / "command-center/synthesis/SYN-0044.diagram-set.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0044-probe2 {msg}")
    return 1


def naive_cached_render(nodes, edges, cache: dict) -> str:
    """Mutant: ignores later graph edits once a diagram has been drawn once."""
    key = "diagram"
    if key not in cache:
        cache[key] = G.render_mermaid("dep", nodes, edges, "cached")
    return cache[key]


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    errs = SL.errors(doc)
    if errs:
        return fail(f"schema {errs[0]}")

    before = G.gated_snapshot(REPO)
    dep = G.load_dependency_source(REPO)
    orig = G.render_mermaid("dep", dep["nodes"], dep["edges"], "orig")
    mut_nodes, mut_edges = G.mutate_graph(dep["nodes"], dep["edges"])
    honest = G.render_mermaid("dep", mut_nodes, mut_edges, "mut")
    cache: dict = {}
    naive_before = naive_cached_render(dep["nodes"], dep["edges"], cache)
    naive_after = naive_cached_render(mut_nodes, mut_edges, cache)

    print(
        f"honest_changed={orig != honest} planted_in_mut={'SYN-0044-PLANTED' in honest} "
        f"naive_changed={naive_before != naive_after}"
    )
    if orig == honest:
        return fail("honest renderer did not change after a graph edit")
    if "SYN-0044-PLANTED" not in honest:
        return fail("planted node missing from regenerated diagram")
    if "SYN-0044-PLANTED" in orig:
        return fail("planted node leaked into the original diagram")
    if naive_before != naive_after:
        return fail("naive cached mutant unexpectedly changed; both-states collapsed")
    if naive_after == honest:
        return fail("naive mutant agrees with honest regeneration")

    G.build_diagrams(REPO)
    after = G.gated_snapshot(REPO)
    if after != before:
        return fail(f"generator wrote/changed {G.GATED}: {before} -> {after}")
    if (REPO / G.GATED).is_file() and not before["present"]:
        return fail("generator created DEPENDENCY-GRAPH.json")

    gate = G.parity_gate_of(doc)
    if gate.get("generator_wrote") is not False or gate.get("bytes_unchanged") is not True:
        return fail("artifact parity_gate does not record a clean gate")
    if gate.get("present_before") != before["present"] or gate.get("present_after") != after["present"]:
        return fail("artifact parity presence disagrees with live snapshot")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    regen = tests.get("test_regeneration_after_a_graph_edit_changes_the_diagram") or {}
    nowrite = tests.get("test_generator_does_not_write_to_DEPENDENCY_GRAPH_json") or {}
    if regen.get("result") != "PASS" or nowrite.get("result") != "PASS":
        return fail("artifact tests not PASS")

    print(
        f"gated_present={before['present']} bytes_unchanged=True "
        f"orig_bytes={len(orig)} mut_bytes={len(honest)}"
    )
    print("SUCCESS:SYN-0044-probe2 regeneration changes diagram; gated file untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
