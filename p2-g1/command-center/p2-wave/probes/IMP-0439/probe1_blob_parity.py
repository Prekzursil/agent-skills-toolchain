"""CRLF/LF blob parity across all fourteen manifest entries (IMP-0439).

Runs blob.py's own temp-repo parity experiment: the blob route yields
identical digests on a CRLF and an LF worktree; the working-tree route
DIFFERS for all fourteen, proving the fix changed something.
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


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        report = blob.parity_experiment(Path(td))

    rows = report.get("rows") or []
    assert report["blob_route_identical_crlf_vs_lf"] is True
    assert report["working_tree_route_differs_for_all_14"] is True
    assert report["blob_equals_recorded_for_all_14"] is True
    assert report["n_entries"] == len(blob.MANIFEST_FILENAMES) == 14
    assert len(rows) == 14

    sample = rows[0]
    assert sample["blob_sha256"] == sample["recorded_provenance_sha256"]
    assert sample["working_tree_sha256"] != sample["blob_sha256"]

    print(json.dumps({
        "probe": "probe1-blob-parity",
        "unit_id": "IMP-0439",
        "entries": report["n_entries"],
        "crlf_materialised": report["n_crlf_rewritten"],
        "blob_route_identical_crlf_vs_lf": report["blob_route_identical_crlf_vs_lf"],
        "worktree_route_differs_all_14": report["working_tree_route_differs_for_all_14"],
        "blob_equals_recorded_all_14": report["blob_equals_recorded_for_all_14"],
        "sample_path": sample["path"],
        "sample_blob_sha256": sample["blob_sha256"],
        "sentinel": "SENTINEL:IMP-0439:PROVENANCE-BLOB-HASHED",
    }, indent=2))
    print("SUCCESS:IMP-0439-probe1 blob route identical across CRLF/LF; "
          "worktree route differs for all fourteen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
