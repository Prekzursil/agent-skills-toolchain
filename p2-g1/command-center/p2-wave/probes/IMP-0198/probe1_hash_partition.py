"""IMP-0198 probe 1 (source): partition membership is a pure function of
SHA-256(salt || canonical identity). An independent second implementation
agrees on every case; a full rebuild is identical; relabelling the cached
convention field moves 0 cases.

Exit 0 iff all three hold across the whole corpus.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.evals.matched_corpus import (HELD_OUT, VISIBLE, independent_partition,  # noqa: E402
                                            load_corpus, partition_of, stratum_counts)

RAW = HERE / "probe1-hash-partition.raw.txt"

corpus = load_corpus()
cases = corpus["cases"]

# Independent recomputation with a mechanically different implementation.
agreements = sum(1 for c in cases
                 if partition_of(c) == independent_partition(c["id"]))

# Rebuild determinism: two full passes agree case-for-case.
first = [partition_of(c) for c in cases]
second = [partition_of(c) for c in cases]
rebuild_identical = first == second

# Convention mutation: relabel the cached field on every case; membership must
# not move (the label is a convention, the hash is the authority).
flipped = [dict(c, partition_cached=(HELD_OUT if partition_of(c) == VISIBLE else VISIBLE))
           for c in cases]
convention_moves = sum(1 for orig, mut in zip(cases, flipped)
                       if partition_of(orig) != partition_of(mut))

strata = stratum_counts(corpus)
n_held = sum(1 for p in first if p == HELD_OUT)
n_vis = len(cases) - n_held
lines = [json.dumps({"probe": "probe1-hash-partition", "unit_id": "IMP-0198",
                     "n_cases": len(cases), "n_held_out": n_held, "n_visible": n_vis,
                     "independent_agreements": agreements,
                     "rebuild_identical": rebuild_identical,
                     "convention_moves": convention_moves,
                     "stratum_counts": {k: {"visible": v[VISIBLE], "held_out": v[HELD_OUT]}
                                        for k, v in strata.items()}})]
assert agreements == len(cases), f"independent recomputation agreed on {agreements}/{len(cases)}"
assert rebuild_identical, "rebuild is not deterministic"
assert convention_moves == 0, "relabelling the convention field moved membership"
assert n_held > 0 and n_vis > 0, "degenerate partition"
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"n_cases": len(cases), "held_out": n_held,
                              "visible": n_vis, "independent_agreements": agreements,
                              "rebuild_identical": True, "convention_moves": 0,
                              "strata": {k: v for k, v in strata.items()}}))
print("SUCCESS:IMP-0198-probe1 held-out partition is hash-determined and reproducible")
