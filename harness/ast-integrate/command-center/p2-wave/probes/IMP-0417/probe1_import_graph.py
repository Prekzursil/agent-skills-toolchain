#!/usr/bin/env python3
"""Probe 1: import-graph + before/after census of independent completion checks.

Signal (1): every named fan-in site imports completion.reducer.judge (same
object). Signal (2): AST census of the live sites is empty; the same census
over fixtures/before finds one local predicate per site.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[3] / "tools"))

from completion.census import census_dir, import_graph_site  # noqa: E402
from completion.sites import SITE_FILES, SITE_IDS, load_all  # noqa: E402
from scenario import BEFORE_DIR, REPO, SITES_DIR  # noqa: E402

sys.path.insert(0, str(REPO / "tools" / "completion" / "tests"))
import test_import_graph as live_tests  # noqa: E402


def main() -> int:
    modules = load_all()
    graphs = []
    for site_id in SITE_IDS:
        path = REPO / SITE_FILES[site_id]
        graph = import_graph_site(path)
        graph["site_id"] = site_id
        graphs.append(graph)
        if not graph["ok"]:
            print(json.dumps({"pass": False, "failed_graph": graph}, sort_keys=True))
            print("FAILED:IMP-0417-probe1 import-graph", site_id)
            return 1
        if modules[site_id].judge is not modules[SITE_IDS[0]].judge:
            print("FAILED:IMP-0417-probe1 judge object identity", site_id)
            return 1

    before = census_dir(BEFORE_DIR, root=REPO, detector="ast")
    after = census_dir(SITES_DIR, root=REPO, detector="ast")
    before_files = sorted({h["path"] for h in before})
    independent_before = len(before_files)
    independent_after = len({h["path"] for h in after})
    if independent_before < 7:
        print(
            json.dumps(
                {"pass": False, "before": before, "after": after},
                indent=2,
                sort_keys=True,
            )
        )
        print("FAILED:IMP-0417-probe1 before census too small", independent_before)
        return 1
    if after:
        print(json.dumps({"pass": False, "after": after}, indent=2, sort_keys=True))
        print("FAILED:IMP-0417-probe1 live sites retain local predicates")
        return 1

    live_tests.test_seven_sites_import_shared_judge()
    live_tests.test_live_sites_have_zero_independent_checks()
    live_tests.test_exit_zero_alone_is_incomplete()
    live_tests.test_digest_without_file_is_incomplete()
    live_tests.test_complete_requires_stat_and_all_flags()

    payload = {
        "probe": "probe1-import-graph",
        "unit_id": "IMP-0417",
        "sites": list(SITE_IDS),
        "import_graph": graphs,
        "judge_object_ids": [id(modules[s].judge) for s in SITE_IDS],
        "before_count": independent_before,
        "after_count": independent_after,
        "before_hit_records": len(before),
        "before_files": before_files,
        "after_hits": after,
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"before={independent_before} after={independent_after} sites={len(SITE_IDS)} "
        "shared-judge=1"
    )
    print("SUCCESS:IMP-0417-probe1 import-graph and before/after census")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
