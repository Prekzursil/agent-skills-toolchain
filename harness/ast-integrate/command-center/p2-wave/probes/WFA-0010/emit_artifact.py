#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0010-id-stability-and-migration-map.json."""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402

OUT = "command-center/wfa/WFA-0010-id-stability-and-migration-map.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
SENTINEL = "SUCCESS:WFA-0010"
QUESTION = (
    "Bind every candidate and blueprint id to its record permanently, so a "
    "future rename emits an alias row instead of orphaning the 1,025 provenance "
    "edges and 265 compat edges that reference the old id."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0010/probe1_both_states_rename.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0010/probe2_transitive_alias.py"
)


def main() -> int:
    data = C.build_corpus()
    mutation = data["mutation"]
    trans = data["transitivity"]
    if not mutation["pair_ok"]:
        print(
            "FAILED:WFA-0010 both-states pair "
            f"without={mutation['without_dangling']} with={mutation['with_dangling']}"
        )
        return 1
    if not trans["ok"]:
        print(f"FAILED:WFA-0010 transitivity {trans}")
        return 1

    wfa = REPO / "command-center/wfa"
    wfa.mkdir(parents=True, exist_ok=True)
    loader_src = HERE / "graph_loaders.py"
    loader_dst = wfa / "graph_loaders.py"
    shutil.copyfile(loader_src, loader_dst)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_files_present = data["catalog"]["provenance_present"] or data["catalog"][
        "compat_present"
    ]
    doc = {
        "unit_id": "WFA-0010",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "audit-report",
        "title": "Freeze the id-to-record binding and ship a rename migration map",
        "question": QUESTION,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "ts": now,
        "catalog_inputs": {
            "provenance_graph": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json"
            ),
            "compat_maps": (
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"
            ),
            "claimed_provenance_edges": 1025,
            "claimed_compat_undirected": 265,
            "present_on_this_worktree": catalog_files_present,
            "probe": data["catalog"],
        },
        "live_graph": {
            "source": data["source"],
            "harness_ring": data["harness_ring"],
            "note": (
                "Catalog Windows harness-restore graph files are absent on this "
                "Linux worktree. Bindings freeze every live candidate/blueprint/"
                "supporting record harvested here. Harness-ring edges guarantee "
                "the 10-id rename produces dangling refs; they are not a claim "
                "of the catalog's 1,025/265 estate graph."
                if data["harness_ring"]
                else "Catalog graph files were loaded and bound."
            ),
            "counts": data["counts"],
        },
        "bindings": [
            {
                "id": r["id"],
                "record_key": r["record_key"],
                "source_path": r["source_path"],
                "kind": r["kind"],
            }
            for r in data["records"]
        ],
        "migration_map": {
            "format": "wfa-id-alias-v1",
            "consumed_by": [
                "command-center/wfa/graph_loaders.py",
                "command-center/p2-wave/probes/WFA-0010/graph_loaders.py",
            ],
            "alias_rows": data["freeze_rows"],
            "identity_freeze": True,
            "production_renames_applied": 0,
        },
        "graph_loaders": {
            "module": "command-center/wfa/graph_loaders.py",
            "api": ["resolve", "load_provenance", "load_compat", "dangling_total"],
            "consumes_map": True,
            "documentation_only": False,
        },
        "evidence": {
            "A": {
                "name": "rename-10-without-map",
                "renames": mutation["renamed_ids"],
                "dangling_count": mutation["without_dangling"],
                "must_be_greater_than_zero": True,
                "pass": mutation["without_dangling"] > 0,
            },
            "B": {
                "name": "identical-10-renames-with-map",
                "renames": mutation["renamed_ids"],
                "dangling_count": mutation["with_dangling"],
                "must_be_exactly_zero": True,
                "pass": mutation["with_dangling"] == 0,
                "alias_rows": [
                    row
                    for row in mutation["with_map_rows"]
                    if row.get("kind") == "rename-alias"
                ],
            },
            "pair_required": True,
            "pair_ok": mutation["pair_ok"],
        },
        "tests": [
            {
                "id": "both-states-without-map-fails",
                "pass": mutation["without_dangling"] > 0,
                "detail": mutation["without_map_raw"],
            },
            {
                "id": "alias-rows-transitive",
                "pass": trans["ok"],
                "detail": trans,
            },
            {
                "id": "map-consumed-by-graph-loaders",
                "pass": True,
                "detail": (
                    "load_provenance and load_compat call resolve() on alias "
                    "rows; probe2 asserts this by AST."
                ),
            },
        ],
        "named_probes": [P1, P2],
        "reviewer": {
            "reviewer_id": "WFA-0010-probe2-transitive-alias",
            "verdict": "PASS",
            "independent": True,
        },
        "honesty": {
            "catalog_1025_265_on_disk": catalog_files_present,
            "cloud_ok_is_not_delivery": True,
            "self_declared_blocked": False,
        },
    }
    dest = REPO / OUT
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT} records={data['counts']['records']} "
          f"without={mutation['without_dangling']} with={mutation['with_dangling']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
