#!/usr/bin/env python3
"""Probe 2: independent reference-graph recomputation of dangling and orphan sets.

Does not trust the linter's internal sets. Recomputes dangling/orphan via
os.walk of objects/ plus a raw JSON read of index.json (independent_graph.py
does not import index_linter).

Also confirms the linter source actually reads the blob store (list_object_paths
+ digest_file) and that scripts/plugin_registry_doctor.py supersedes the
historical doctor by delegation rather than by duplicating the algorithm.

This is evidence signal (2) from the catalog.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

import index_linter as linter  # noqa: E402
from independent_graph import independent_reference_graph  # noqa: E402


def main() -> int:
    linter_src = (REPO / "tools" / "marketplace" / "index_linter.py").read_text(
        encoding="utf-8"
    )
    doctor_src = (REPO / "scripts" / "plugin_registry_doctor.py").read_text(
        encoding="utf-8"
    )
    reads_store = "list_object_paths" in linter_src and "digest_file" in linter_src
    doctor_ok = (
        "SUPERSEDES" in doctor_src
        and "index_linter" in doctor_src
        and "list_object_paths" not in doctor_src
        and "digest_file" not in doctor_src
        and 'DELEGATES_TO = "tools/marketplace/index_linter.py"' in doctor_src
    )

    with tempfile.TemporaryDirectory(prefix="imp-0114-p2-") as td:
        root = Path(td)
        _store, _index, planted = linter.plant_one_of_each_defect(root / "dirty")
        dirty = linter.lint_root(root / "dirty")
        graph = independent_reference_graph(root / "dirty")

        linter.plant_clean(root / "clean")
        clean = linter.lint_root(root / "clean")
        clean_graph = independent_reference_graph(root / "clean")

        dangling_match = set(graph["dangling_digests"]) == dirty.dangling_digests
        orphan_match = set(graph["orphan_digests"]) == dirty.orphan_digests
        planted_orphan_in_graph = planted["orphan_digest"] in set(graph["orphan_digests"])
        planted_dangle_in_graph = planted["dangling_digest"] in set(
            graph["dangling_digests"]
        )
        clean_agree = (
            clean_graph["dangling_digests"] == []
            and clean_graph["orphan_digests"] == []
            and clean.dangling_digests == set()
            and clean.orphan_digests == set()
            and clean.clean
        )
        independent = "os.walk" in graph["method"]
        result = {
            "probe": "probe2-independent-reference-graph",
            "unit_id": "IMP-0114",
            "dangling_match": dangling_match,
            "orphan_match": orphan_match,
            "planted_orphan_in_graph": planted_orphan_in_graph,
            "planted_dangle_in_graph": planted_dangle_in_graph,
            "graph_dangling": graph["dangling_digests"],
            "linter_dangling": sorted(dirty.dangling_digests),
            "graph_orphans": graph["orphan_digests"],
            "linter_orphans": sorted(dirty.orphan_digests),
            "graph_method": graph["method"],
            "independent_method": independent,
            "linter_reads_blob_store": reads_store,
            "doctor_supersedes_by_delegation": doctor_ok,
            "clean_agree": clean_agree,
            "dirty_walked_blob_store": dirty.walked_blob_store,
            "pass": (
                dangling_match
                and orphan_match
                and planted_orphan_in_graph
                and planted_dangle_in_graph
                and independent
                and reads_store
                and doctor_ok
                and clean_agree
                and dirty.walked_blob_store
            ),
        }
        print(json.dumps(result, sort_keys=True))
        print(
            f"dangling_match={dangling_match} orphan_match={orphan_match} "
            f"reads_store={reads_store} doctor_ok={doctor_ok} clean_agree={clean_agree}"
        )
        if not result["pass"]:
            print(
                "FAILED:IMP-0114-probe2 independent graph disagreed or doctor duplicated"
            )
            return 1
        print(
            "SUCCESS:IMP-0114-probe2 independent graph matches dangling/orphan sets; "
            "linter reads the blob store; doctor supersedes by delegation"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
