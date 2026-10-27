"""Phase 8 - skill and capability routing (`_USER-PROMPTS.md:10948-10963`).

Module map:

  `index.py`        discover + normalize every routable unit (912 measured at HEAD)
  `descriptions.py` score descriptions AS ROUTING ARTIFACTS; synthesize aliases
  `rules.py`        deterministic high-precision lanes + anti-trigger demotion
  `semantic.py`     hermetic lexical-semantic recall (BM25 + char n-gram + concepts)
  `router.py`       fusion, calibrated confidence, top-k, conflicts, overrides,
                    explanation, fallback
  `budget.py`       injected-byte accounting - the anti-flooding measurement
  `metrics.py`      precision/recall, skill-use breadth, task-success bookkeeping
  `queries.py`      the labelled query set + its disclosed labelling protocol

The load-bearing invariant, asserted by `test_regression_no_flood.py`: selection
quality and injected bytes are measured SEPARATELY, so "high recall" can never be
bought by injecting more of the corpus.
"""

from __future__ import annotations

__all__ = [
    "budget",
    "descriptions",
    "index",
    "metrics",
    "queries",
    "router",
    "rules",
    "semantic",
]
