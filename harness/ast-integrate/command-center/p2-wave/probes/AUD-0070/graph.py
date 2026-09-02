"""Assemble the AUD-0070 audit-graph from claims + detectors."""
from __future__ import annotations

from typing import Any

import claims as CL
import pairwise as P
import temporal as T


def build() -> dict[str, Any]:
    loaded = CL.load_claims()
    claim_list = loaded["claims"]
    by_id = {c["claim_id"]: c for c in claim_list}
    cands = P.candidates(claim_list)
    mutant = P.candidates(claim_list, always=True)
    edges = T.classify_candidates(by_id, cands)
    blind = T.classify_candidates(by_id, cands, blind=True)

    nodes = []
    for c in claim_list:
        nodes.append(
            {
                "id": c["claim_id"],
                "kind": "claim",
                "object_key": c["object_key"],
                "polarity": c["polarity"],
                "as_of": c["as_of"],
                "namespace": c["namespace"],
                "source": f"{c['source_path']}:{c['source_line']}",
                "span": c["span"],
                "proposition": c["proposition"],
            }
        )
    for ns in loaded["namespaces"]:
        nodes.append(
            {
                "id": ns["id"],
                "kind": "namespace",
                "token_shape": ns["token_shape"],
                "defining_artifact": ns["defining_artifact"],
                "example_ids": ns["example_ids"],
                "note": ns["note"],
            }
        )

    graph_edges = []
    for e in edges:
        graph_edges.append(
            {
                "id": e["id"],
                "source": e["earlier_id"],
                "target": e["later_id"],
                "edge_type": e["edge_type"],
                "object_key": e["object_key"],
                "left_span": e["left_span"],
                "right_span": e["right_span"],
                "left_source": e["left_source"],
                "right_source": e["right_source"],
                "earlier_as_of": e["earlier_as_of"],
                "later_as_of": e["later_as_of"],
            }
        )

    known = next(
        e
        for e in graph_edges
        if {e["source"], e["target"]} == {CL.KNOWN_A, CL.KNOWN_B}
    )
    return {
        "loaded": loaded,
        "candidates": cands,
        "mutant_pair_count": len(mutant),
        "true_candidate_count": len(cands),
        "nodes": nodes,
        "edges": graph_edges,
        "blind_edges": blind,
        "known_edge": known,
        "by_id": by_id,
        "counts": {
            "claims": len(claim_list),
            "nodes": len(nodes),
            "edges": len(graph_edges),
            "contradiction": sum(1 for e in graph_edges if e["edge_type"] == "CONTRADICTION"),
            "superseded": sum(1 for e in graph_edges if e["edge_type"] == "SUPERSEDED"),
            "namespaces": len(loaded["namespaces"]),
        },
    }
