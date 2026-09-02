"""Live scoring helper for IMP-0313 probes and receipt emission."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from corpus import GOLD, TRANSCRIPT, ensure_fixtures, load_fixtures  # noqa: E402
from tools.council.artifacts.argument_graph import (  # noqa: E402
    build_argument_graph,
    precision_recall,
    validate_graph,
)


def live_scores() -> dict:
    ensure_fixtures()
    turns, gold = load_fixtures()
    graph = build_argument_graph(turns)
    validate_graph(graph, turns)
    scores = precision_recall(graph.edges, gold)
    poison = [
        e
        for e in graph.edges
        if e.source in {"c998", "c999"} or e.target in {"c998", "c999"}
    ]
    unresolved = []
    turn_ids = {t["turn_id"] for t in turns}
    for edge in graph.edges:
        if edge.turn_id not in turn_ids:
            unresolved.append(edge.turn_id)
    return {
        "n_turns": len(turns),
        "n_claims": len(graph.claims),
        "n_pred": len(graph.edges),
        "n_gold": len(gold),
        "precision": scores["precision"],
        "recall": scores["recall"],
        "true_positives": scores["true_positives"],
        "false_positives": scores["false_positives"],
        "false_negatives": scores["false_negatives"],
        "false_positive_keys": scores["false_positive_keys"],
        "false_negative_keys": scores["false_negative_keys"],
        "poison_edges": len(poison),
        "unresolved_turn_ids": unresolved,
        "transcript_path": str(TRANSCRIPT.relative_to(REPO).as_posix()),
        "gold_path": str(GOLD.relative_to(REPO).as_posix()),
        "graph": graph,
        "turns": turns,
        "gold": gold,
        "scores": scores,
    }
