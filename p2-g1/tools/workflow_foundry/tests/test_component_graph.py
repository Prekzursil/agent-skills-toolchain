"""Library tests for component_graph."""
from __future__ import annotations

from workflow_foundry.component_graph import (
    OrphanComponentError,
    assemble,
    assert_no_orphans,
    build,
    is_orphan,
    orphan_count,
)


def run_all() -> dict:
    empty_ok = orphan_count({"nodes": []}) == 0
    node = {
        "id": "n1",
        "kind": "retrieve",
        "provenance": [
            {
                "candidate_id": "c1",
                "source_span": {"uri": "x.yaml", "start_line": 1},
            }
        ],
    }
    anchored = not is_orphan(node)
    bare = is_orphan({"id": "x", "kind": "k", "provenance": []})
    raised = False
    try:
        assert_no_orphans({"nodes": [{"id": "o", "kind": "k", "provenance": []}]})
    except OrphanComponentError:
        raised = True
    return {
        "pass": empty_ok and anchored and bare and raised,
        "empty_ok": empty_ok,
        "anchored": anchored,
        "bare_orphan": bare,
        "assert_raises": raised,
    }
