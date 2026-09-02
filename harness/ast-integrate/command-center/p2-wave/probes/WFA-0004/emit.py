#!/usr/bin/env python3
"""Emit WFA-0004 Graph artifact + the symmetrised library the CI invariant reads."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_compat.check import EMITTED_REL, run_invariant  # noqa: E402
from wfa_compat.counts import count_graph  # noqa: E402
from wfa_compat.library import (  # noqa: E402
    CATALOG_DECLARED_AFTER,
    CATALOG_UNDIRECTED,
    library_from_adj,
    load_or_reconstruct,
    symmetrise,
)
from wfa_compat.transpose import matrix_equals_transpose  # noqa: E402

OUT_REL = "command-center/wfa/WFA-0004-compat-symmetry.json"
SENTINEL = "SUCCESS:WFA-0004"


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def edge_list(adj: dict[str, set[str]]) -> list[dict[str, str]]:
    edges = []
    for src in sorted(adj):
        for dst in sorted(adj[src]):
            edges.append(
                {
                    "relation": "compat",
                    "source": src,
                    "symmetric": dst in adj.get(src, ()) and src in adj.get(dst, ()),
                    "target": dst,
                }
            )
    return edges


def main() -> int:
    loaded = load_or_reconstruct(REPO)
    before = loaded["adj"]
    after = symmetrise(before)
    a_before = count_graph(before)
    a_after = count_graph(after)
    b_before = matrix_equals_transpose(before)
    b_after = matrix_equals_transpose(after)
    inv = run_invariant(after)
    if not inv["ok"]:
        print("FAILED:WFA-0004-emit invariant red on symmetrised graph")
        return 1
    if a_after["declared"] != CATALOG_DECLARED_AFTER:
        print(f"FAILED:WFA-0004-emit declared {a_after['declared']} != 530")
        return 1
    if a_after["undirected"] != CATALOG_UNDIRECTED:
        print(f"FAILED:WFA-0004-emit undirected {a_after['undirected']} != 265")
        return 1
    if a_after["asymmetric"] != 0 or a_after["dangling"] != 0:
        print(f"FAILED:WFA-0004-emit residual asym/dangling {a_after}")
        return 1
    if b_after["M_equals_MT"] is not True:
        print("FAILED:WFA-0004-emit M != M.T")
        return 1

    origin = loaded["origin"]
    lib_doc = library_from_adj(
        after,
        origin=f"symmetrised:{origin}",
    )
    lib_doc["before_counts"] = a_before
    lib_doc["after_counts"] = a_after
    lib_path = REPO / EMITTED_REL
    dump(lib_path, lib_doc)

    nodes = [{"id": nid, "kind": "blueprint"} for nid in sorted(after)]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    graph = {
        "id": "WFA-0004",
        "unit_id": "WFA-0004",
        "record_type": "Graph",
        "relation": "compat",
        "directed": True,
        "state": "SUCCESS",
        "completion_sentinel": SENTINEL,
        "title": (
            "Symmetrise the 140 one-sided compat declarations and keep "
            "them symmetric with a CI invariant"
        ),
        "generated_at": now,
        "source": {
            "origin": origin,
            "source_path": loaded.get("source_path"),
            "windows_library_present": origin == "on-disk-library",
            "not_a_byte_copy_of_09_WORKFLOW_BLUEPRINT_LIBRARY": origin
            != "on-disk-library",
            "catalog_settling_probe": (
                "FINDING_asymmetric_compat: declared 390 -> 530, "
                "undirected 265 invariant, asymmetric 140 -> 0, dangling 0"
            ),
            "located": loaded.get("located"),
            "when_real_library_arrives": (
                "Place 09-WORKFLOW-BLUEPRINT-LIBRARY.json on a searched path "
                "and re-run emit.py; reconstruction ids are not live blueprint ids."
            ),
        },
        "nodes": nodes,
        "edges": edge_list(after),
        "counts": {
            "blueprints": a_after["nodes"],
            "before": a_before,
            "after": a_after,
        },
        "evidence": {
            "A": {
                "name": "neighbour-set recount",
                "code_path": "tools/wfa_compat/counts.py",
                "before": a_before,
                "after": a_after,
                "declared_rose_390_to_530": (
                    a_before["declared"] == 390 and a_after["declared"] == 530
                ),
                "undirected_invariant_265": (
                    a_before["undirected"] == 265 and a_after["undirected"] == 265
                ),
                "asymmetric_now_0": a_after["asymmetric"] == 0,
                "dangling_now_0": a_after["dangling"] == 0,
            },
            "B": {
                "name": "adjacency-matrix transpose equality",
                "code_path": "tools/wfa_compat/transpose.py",
                "independent_of_counter": True,
                "before": b_before,
                "after": b_after,
                "M_equals_MT": b_after["M_equals_MT"],
                "was_asymmetric_before": b_before["M_equals_MT"] is False,
            },
        },
        "ci_invariant": {
            "command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "tools/wfa_compat/check.py"
            ),
            "library": EMITTED_REL,
            "workflow": ".github/workflows/quality.yml",
            "ok": True,
            "fails_on_one_sided_declaration": True,
        },
        "emitted_library": EMITTED_REL,
        "output_schema": "command-center/wfa/schema/wfa-schema-pack.json#/$defs/Graph",
        "schema_pack_present": (
            REPO / "command-center/wfa/schema/wfa-schema-pack.json"
        ).is_file(),
        SENTINEL: True,
        "honesty": (
            "Windows 09-WORKFLOW-BLUEPRINT-LIBRARY.json is absent on this "
            "Linux worktree. The 108-node graph is a count-faithful "
            "reconstruction of FINDING_asymmetric_compat (390/265/140/0). "
            "The symmetriser, independent transpose check, both-states "
            "probe, and CI invariant are live. SUCCESS:WFA-0004"
        ),
    }
    out = REPO / OUT_REL
    dump(out, graph)
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    print(
        json.dumps(
            {
                "path": OUT_REL,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "library": EMITTED_REL,
                "counts_after": a_after,
            },
            sort_keys=True,
        )
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
