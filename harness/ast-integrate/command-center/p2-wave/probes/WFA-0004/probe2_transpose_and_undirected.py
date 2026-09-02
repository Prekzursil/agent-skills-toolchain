#!/usr/bin/env python3
"""Probe 2: independent transpose check + undirected/dangling invariance.

Signal A (counts.py): declared 390->530, undirected 265/265, asymmetric 140->0,
dangling 0 after.
Signal B (transpose.py): M == M.T after symmetrisation, and M != M.T before.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_compat.counts import count_graph  # noqa: E402
from wfa_compat.library import (  # noqa: E402
    CATALOG_ASYMMETRIC,
    CATALOG_DECLARED,
    CATALOG_DECLARED_AFTER,
    CATALOG_UNDIRECTED,
    load_or_reconstruct,
    symmetrise,
)
from wfa_compat.transpose import matrix_equals_transpose  # noqa: E402

GRAPH_REL = "command-center/wfa/WFA-0004-compat-symmetry.json"


def fail(msg: str, extra: dict | None = None) -> int:
    if extra:
        print(json.dumps(extra, sort_keys=True, default=str))
    print(f"FAILED:WFA-0004-probe2 {msg}")
    return 1


def main() -> int:
    loaded = load_or_reconstruct(REPO)
    before = loaded["adj"]
    after = symmetrise(before)
    a_before = count_graph(before)
    a_after = count_graph(after)
    b_before = matrix_equals_transpose(before)
    b_after = matrix_equals_transpose(after)

    if a_before["undirected"] != a_after["undirected"]:
        return fail(
            "undirected count moved across symmetrisation",
            {"before": a_before, "after": a_after},
        )
    if a_before["undirected"] != CATALOG_UNDIRECTED:
        return fail(
            f"undirected != {CATALOG_UNDIRECTED}",
            {"before": a_before, "after": a_after},
        )
    if a_after["dangling"] != 0 or a_before["dangling"] != 0:
        return fail("dangling refs present", {"before": a_before, "after": a_after})
    if a_before["declared"] != CATALOG_DECLARED:
        return fail("before declared != 390", {"before": a_before})
    if a_after["declared"] != CATALOG_DECLARED_AFTER:
        return fail("after declared != 530", {"after": a_after})
    if a_before["asymmetric"] != CATALOG_ASYMMETRIC:
        return fail("before asymmetric != 140", {"before": a_before})
    if a_after["asymmetric"] != 0:
        return fail("after asymmetric != 0", {"after": a_after})
    if b_before["M_equals_MT"] is True:
        return fail("transpose equal before symmetrisation (counterfeit)", b_before)
    if b_after["M_equals_MT"] is not True:
        return fail("transpose not equal after symmetrisation", b_after)
    if b_after["code_path"] == "tools/wfa_compat/counts.py":
        return fail("transpose check used the counter path")

    graph_path = REPO / GRAPH_REL
    if graph_path.is_file():
        doc = json.loads(graph_path.read_text(encoding="utf-8"))
        after_block = ((doc.get("counts") or {}).get("after")) or {}
        if after_block.get("declared") != CATALOG_DECLARED_AFTER:
            return fail("artifact after.declared mismatch", {"artifact": after_block})
        if after_block.get("undirected") != CATALOG_UNDIRECTED:
            return fail("artifact after.undirected mismatch", {"artifact": after_block})
        if after_block.get("asymmetric") != 0:
            return fail("artifact after.asymmetric mismatch", {"artifact": after_block})
        evidence_b = (doc.get("evidence") or {}).get("B") or {}
        if evidence_b.get("M_equals_MT") is not True:
            return fail("artifact evidence B not transpose-equal", evidence_b)

    payload = {
        "pass": True,
        "probe": "probe2-transpose-and-undirected",
        "unit_id": "WFA-0004",
        "origin": loaded["origin"],
        "signal_A_before": a_before,
        "signal_A_after": a_after,
        "signal_B_before": b_before,
        "signal_B_after": b_after,
        "undirected_invariant": True,
        "dangling_after": 0,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:WFA-0004-probe2 undirected=265 invariant; dangling=0; "
        "M==M.T after via independent transpose path"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
