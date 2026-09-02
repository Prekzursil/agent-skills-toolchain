#!/usr/bin/env python3
"""Named probe 1: blob route identical on CRLF vs LF; working-tree route differs.

All fourteen contracted manifest entries. The Windows checkout is simulated by
rewriting the worktree to CRLF after an LF commit (core.autocrlf materialisation
without a Windows box). Independent of probe 2.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import blob  # noqa: E402
import render  # noqa: E402


def fail(msg: str, extra: dict | None = None) -> int:
    print(f"FAILED:IMP-0439-probe1 {msg}")
    if extra:
        print(json.dumps(extra, indent=2, default=str)[:8000])
    return 1


def main() -> int:
    if blob.MANIFEST_FILENAMES != render.CONTRACTED_ARTIFACTS:
        return fail(
            "MANIFEST_FILENAMES drifted from render.CONTRACTED_ARTIFACTS",
            {
                "blob": list(blob.MANIFEST_FILENAMES),
                "render": list(render.CONTRACTED_ARTIFACTS),
            },
        )
    if len(blob.MANIFEST_FILENAMES) != 14:
        return fail(f"expected 14 manifest entries, got {len(blob.MANIFEST_FILENAMES)}")

    with tempfile.TemporaryDirectory(prefix="imp0439-p1-") as tmp:
        result = blob.parity_experiment(Path(tmp))

    table_path = HERE / "probe1-digest-table.json"
    table_path.write_text(
        json.dumps(
            {
                "columns": [
                    "path",
                    "working_tree_sha256",
                    "blob_sha256",
                    "recorded_provenance_sha256",
                ],
                "n": result["n_entries"],
                "n_crlf_rewritten": result["n_crlf_rewritten"],
                "blob_route_identical_crlf_vs_lf": result[
                    "blob_route_identical_crlf_vs_lf"
                ],
                "working_tree_route_differs_for_all_14": result[
                    "working_tree_route_differs_for_all_14"
                ],
                "rows": result["rows"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if result["n_entries"] != 14:
        return fail("not 14 rows", result)
    if result["n_crlf_rewritten"] != 14:
        return fail("CRLF rewrite did not touch all 14 files", result)
    if not result["blob_route_identical_crlf_vs_lf"]:
        return fail("blob hashes diverged across CRLF vs LF worktrees", result)
    if not result["blob_equals_recorded_for_all_14"]:
        return fail("blob hash != recorded provenance hash", result)
    if not result["working_tree_route_differs_for_all_14"]:
        return fail(
            "working-tree route did not differ — control is dead, blob-route "
            "green would be silence in both states",
            result,
        )
    if not result["independent_git_show_matches_cat_file"]:
        return fail("git show did not match git cat-file", result["independent_samples"])

    payload = {
        "pass": True,
        "probe": "probe1-blob-parity",
        "unit_id": "IMP-0439",
        "n_entries": result["n_entries"],
        "blob_route_identical_crlf_vs_lf": True,
        "working_tree_route_differs_for_all_14": True,
        "independent_git_show_matches_cat_file": True,
        "table_path": str(table_path.relative_to(REPO)),
        "independent_samples": result["independent_samples"],
    }
    print(json.dumps(payload, indent=2))
    print(
        "n=14 blob_identical=True working_tree_differs=True "
        f"git_show_matches_cat_file=True table={payload['table_path']}"
    )
    print("SUCCESS:IMP-0439-probe1 blob-parity fourteen-entry table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
