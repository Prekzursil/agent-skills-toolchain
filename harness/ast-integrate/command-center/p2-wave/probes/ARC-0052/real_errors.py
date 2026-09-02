"""Three live error strings that fail the A8 contract, plus required rewrites.

Needles are unique substrings in shipped source. Line numbers are measured at
emit time and re-checked by probe2; a moved needle is a live miss, not a skip.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# before_emitted is the owner-visible string (or its template) as shipped.
REAL_ERRORS: list[dict[str, Any]] = [
    {
        "id": "E1-unit-manifest-empty-walk",
        "path": "tools/command-center/unit_manifest.py",
        "needle": 'raise ManifestError("discovered ZERO receipts (empty walk)")',
        "before": "FAILED:unit-manifest discovered ZERO receipts (empty walk)",
        "after": {
            "happened": (
                "unit-manifest walked the receipts tree and found zero receipt JSON files."
            ),
            "means": (
                "completion condition 11 cannot be derived; the artifact register is empty, "
                "not merely out of date."
            ),
            "next_action": (
                "emit a per-unit receipt under command-center/p2-wave/probes/<UNIT-ID>/ "
                "or pass the receipts root that actually contains receipts, then re-run "
                "python3 tools/command-center/unit_manifest.py"
            ),
        },
    },
    {
        "id": "E2-validate-graph-missing",
        "path": "tools/command-center/validate.py",
        "needle": 'print(f"FAILED:cc-validate dependency graph missing at {graph_path}")',
        "before": "FAILED:cc-validate dependency graph missing at {graph_path}",
        "after": {
            "happened": (
                "cc-validate loaded the catalog but the dependency graph file is not on disk."
            ),
            "means": (
                "reachability cannot be checked, so catalog and graph would silently drift."
            ),
            "next_action": (
                "write the graph with python3 tools/command-center/close.py --list "
                "(close.py rebuilds DEPENDENCY-GRAPH.json) or cat.build_graph, then re-run "
                "python3 tools/command-center/validate.py"
            ),
        },
    },
    {
        "id": "E3-measure-predicate-absent",
        "path": "command-center/p2-wave/_measure_one_delivered.py",
        "needle": 'return fail(uid, "predicate:absent")',
        "before": "FAILED:delivered ARC-0052 predicate:absent",
        "after": {
            "happened": (
                "G-1 measure for ARC-0052 found a missing probe dir, empty output_path, "
                "or missing per-unit receipts."
            ),
            "means": (
                "the unit is not implemented on this worktree; cloud ok=true is not delivery."
            ),
            "next_action": (
                "create command-center/p2-wave/probes/ARC-0052/, emit "
                "command-center/phase3/A8/DESIGN.json, run the two named probes to exit 0, "
                "then re-run python3 command-center/p2-wave/_measure_one_delivered.py ARC-0052"
            ),
        },
    },
]


def locate(repo: Path, spec: dict[str, Any]) -> dict[str, Any]:
    path = repo / spec["path"]
    text = path.read_text(encoding="utf-8")
    needle = spec["needle"]
    if needle not in text:
        raise FileNotFoundError(f"needle absent in {spec['path']}: {needle}")
    prefix = text.split(needle, 1)[0]
    line_no = prefix.count("\n") + 1
    return {
        "id": spec["id"],
        "path": spec["path"],
        "line": line_no,
        "anchor": f"{spec['path']}:{line_no}",
        "needle": needle,
        "before": spec["before"],
        "after": spec["after"],
    }


def locate_all(repo: Path) -> list[dict[str, Any]]:
    return [locate(repo, spec) for spec in REAL_ERRORS]
