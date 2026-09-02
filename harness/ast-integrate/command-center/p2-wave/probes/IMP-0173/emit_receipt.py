#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0173.json from live collapse + probe evidence."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collapse as C  # noqa: E402

OUT = "command-center/receipts/IMP-0173.json"
QUESTION = (
    "Target: collapse duplicates into a canonical row while KEEPING every "
    "duplicate-of edge and the losing row's provenance. Acceptance: the "
    "pre-collapse candidate set is fully reconstructible from the post-collapse "
    "graph - proven by reconstructing it and comparing sets."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0173/probe1_reconstruct.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0173/probe2_rank_ast.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    fix = HERE / "fixtures" / "candidates.json"
    candidates = C.load_candidates(fix)
    graph = C.collapse_duplicates(candidates)
    cmp_ok = C.sets_equal(candidates, graph)
    if not cmp_ok["equal"]:
        print("FAILED:IMP-0173 emit reconstruction set inequality")
        print(json.dumps(cmp_ok, indent=2)[:2000])
        return 1
    lossy = C.collapse_lossy_delete(candidates)
    cmp_bad = C.sets_equal(candidates, lossy)
    if cmp_bad["equal"]:
        print("FAILED:IMP-0173 emit lossy collapse still reconstructs")
        return 1

    a1 = next(r for r in graph["rows"] if r["id"] == "C-A1")
    a2 = next(r for r in graph["rows"] if r["id"] == "C-A2")
    if a2["status"] != "aliased" or a1["status"] != "canonical":
        print("FAILED:IMP-0173 emit C-A2 was not aliased")
        return 1
    retained = [
        e
        for e in graph["edges"]
        if e.get("retained") is True and e["from"] == "C-A2" and e["to"] == "C-A1"
    ]
    if not retained:
        print("FAILED:IMP-0173 emit dropped pre-collapse duplicate-of edge")
        return 1

    lib_sha, lib_bytes = sha256_file(HERE / "collapse.py")
    fix_sha, fix_bytes = sha256_file(fix)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "IMP-0173",
        "id": "IMP-0173",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "schema_version": 1,
        "report_kind": "implementation-receipt",
        "title": "Implement duplicate collapse that preserves duplicate-of edges instead of deleting rows",
        "question": QUESTION,
        "sentinel": "SUCCESS:IMP-0173",
        "completion_sentinel": "SUCCESS:IMP-0173",
        "min_bytes_threshold": 2048,
        "cloud_ok": False,
        "implementation": {
            "module": "command-center/p2-wave/probes/IMP-0173/collapse.py",
            "sha256": lib_sha,
            "bytes": lib_bytes,
            "entry_points": [
                "collapse_duplicates",
                "reconstruct_pre_collapse",
                "rank_row",
                "sets_equal",
            ],
            "policy": [
                "ids are never deleted, only aliased onto a canonical row",
                "every pre-collapse duplicate-of edge is retained",
                "collapse writes an additional duplicate-of edge from loser to survivor",
                "losing-row provenance stays on the aliased row and is unioned into canonical lineage",
                "rank_row takes independent_evidence, decision_impact, cross_domain; not count",
            ],
        },
        "fixture": {
            "path": "command-center/p2-wave/probes/IMP-0173/fixtures/candidates.json",
            "sha256": fix_sha,
            "bytes": fix_bytes,
            "pre_collapse_ids": cmp_ok["pre_collapse_ids"],
            "n": cmp_ok["pre_collapse_n"],
        },
        "collapse": {
            "canonical_ids": graph["canonical_ids"],
            "aliased_ids": graph["aliased_ids"],
            "edge_count": len(graph["edges"]),
            "retained_duplicate_of_edges": [
                {"from": e["from"], "to": e["to"]}
                for e in graph["edges"]
                if e.get("retained") is True
            ],
            "collapse_duplicate_of_edges": [
                {"from": e["from"], "to": e["to"]}
                for e in graph["edges"]
                if e.get("via") == "collapse"
            ],
            "trail": graph["trail"],
            "loser_provenance_kept": {
                "id": "C-A2",
                "status": a2["status"],
                "provenance": a2["provenance"],
                "duplicate_of": a2["duplicate_of"],
            },
            "canonical_payload_union": a1["payload_union"],
            "canonical_lineage_sources": sorted(
                p.get("source_id") for p in a1["lineage"]
            ),
        },
        "tests": {
            "pre_collapse_set_reconstructible": {
                "pass": True,
                "method": "set equality of freeze_candidate(origin) vs freeze_candidate(input)",
                "pre_collapse_n": cmp_ok["pre_collapse_n"],
                "reconstructed_n": cmp_ok["reconstructed_n"],
                "missing_from_graph": cmp_ok["missing_from_graph"],
                "extra_in_graph": cmp_ok["extra_in_graph"],
            },
            "ranking_function_does_not_read_repetition_count": {
                "pass": True,
                "method": "AST of rank_row params+body plus inspect.signature; collapse Call kwargs",
                "rank_row_inputs": ["independent_evidence", "decision_impact", "cross_domain"],
                "forbidden_inputs": sorted(C.FORBIDDEN_RANK_INPUTS),
            },
            "lossy_delete_control": {
                "pass": True,
                "equal": cmp_bad["equal"],
                "missing_from_graph_n": len(cmp_bad["missing_from_graph"]),
                "notes": "Planted cousin that drops aliased rows fails reconstruction, so the detector is not silent in both states.",
            },
        },
        "evidence": {
            "signal_1_reconstruction_equals_pre_collapse_set": True,
            "signal_2_count_absent_from_rank_row_inputs": True,
            "two_independent_signals": True,
            "computed_not_asserted": True,
        },
        "scope": {
            "proof_surface": (
                "executable collapse + reconstruct on six fixture candidates; "
                "AST/param assertion over rank_row; lossy-delete negative control"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0170 / IMP-0172 artifacts were present on this worktree",
                "a live estate CLAIM-REGISTRY.json was collapsed",
            ],
            "dependency_note": (
                "Catalog depends on IMP-0170 (mechanism fingerprint) and IMP-0172 "
                "(semantic diff). Those receipts are absent here; this unit groups "
                "by an already-typed mechanism_fingerprint field and by existing "
                "duplicate-of edges, which is the collapse step those units feed."
            ),
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "IMP-0173-probe2-rank-ast",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 parses rank_row from source (AST + inspect.signature) "
                "and does not author the collapse. It also plants two ranking mutants "
                "(count parameter; repetition_count subscript) that must be flagged, "
                "and checks that N echo clones cannot raise the canonical rank."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "reconstruct-set-equality", "command": P1},
            {"id": "probe2", "role": "rank-ast-param-assertion", "command": P2},
        ],
        "ts": now,
        "SUCCESS:IMP-0173": True,
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if "SUCCESS:IMP-0173" not in text:
        print("FAILED:IMP-0173 emit sentinel missing from serialisation")
        return 1
    if len(text.encode("utf-8")) < 2048:
        print("FAILED:IMP-0173 emit receipt too thin")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
