"""IMP-0174 probe 2 (source, both-states): a planted orphan FAILS the build.

Detector control. A stage with an empty source span planted into the
extraction makes build() raise OrphanComponentError; the same build
without the plant is green. A lookalike node whose NAME suggests an
orphan but whose span is valid is NOT flagged (false-positive control).

Exit 0 iff the bad state fires and the good states stay silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_WALK = Path(__file__).resolve().parent
REPO = _WALK
for _ in range(6):
    if (_REPO_TEST := _WALK / "command-center" / "p2-wave").is_dir():
        REPO = _WALK
        break
    _WALK = _WALK.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.workflow_foundry.component_graph import (  # noqa: E402
    OrphanComponentError,
    assemble,
    build,
    plant_orphan,
    with_lookalike_named_orphan,
    with_unanchored_stage,
)

BASE = {
    "candidates": [
        {
            "id": "cand.base",
            "stages": [
                {"local_id": "s1", "kind": "ingest",
                 "source_span": {"uri": "sources/base.md", "start_line": 1, "end_line": 5},
                 "contract": {"output_type": "rows"}},
            ],
            "compositions": [],
        }
    ]
}

planted_extraction = with_unanchored_stage(BASE)
fired = False
error_id = ""
try:
    build(planted_extraction)
except OrphanComponentError as exc:
    fired = True
    error_id = exc.error_id

clean_graph = build(BASE)
planted_graph = plant_orphan(clean_graph)

lookalike_graph = assemble(with_lookalike_named_orphan(BASE))
lookalike_orphans = [n for n in lookalike_graph["nodes"] if n["kind"] == "orphan-lookalike"]

checks = {
    "planted_orphan_fails_build": fired and error_id == "orphan-component",
    "clean_build_green": clean_graph["orphan_count"] == 0,
    "planted_graph_counts_orphan": planted_graph["orphan_count"] == 1,
    "planted_id_present": "planted-unanchored-stage" in planted_graph["orphan_ids"],
    "lookalike_named_node_not_orphan": len(lookalike_orphans) == 1
        and lookalike_orphans[0]["id"] not in lookalike_graph["orphan_ids"],
    "lookalike_build_green": lookalike_graph["orphan_count"] == 0,
    "both_states": fired and clean_graph["orphan_count"] == 0,
}

result = {
    "probe": "probe2-planted-orphan",
    "unit_id": "IMP-0174",
    "checks": checks,
    "orphan_count_clean": clean_graph["orphan_count"],
    "orphan_count_planted": planted_graph["orphan_count"],
    "orphan_count_lookalike": lookalike_graph["orphan_count"],
    "error_id": error_id,
    "pass": all(checks.values()),
}
print(json.dumps(result, sort_keys=True))
if not result["pass"]:
    print("FAILED:IMP-0174-probe2 " + ",".join(k for k, v in checks.items() if not v))
    raise SystemExit(1)
print("SUCCESS:IMP-0174-probe2 planted orphan fails the build; lookalike stays green")
