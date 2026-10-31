"""Independent re-derivation: git show vs cat-file vs provenance_bytes (IMP-0439).

Builds its OWN fixture repo (independent of probe1's experiment), then
re-derives two entries' digests with mechanically different commands.
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
    checked = []
    with tempfile.TemporaryDirectory() as td:
        repo = blob.init_manifest_fixture(Path(td))
        rels = [f"command-center/{name}" for name in blob.MANIFEST_FILENAMES]
        blob.materialise_crlf_worktree(repo, rels)
        # A SECOND CRLF rewrite must be idempotent for the blob route.
        n2 = blob.materialise_crlf_worktree(repo, rels)
        assert n2 == len(rels), n2
        for rel in (rels[0], rels[3]):
            show = blob.sha256_hex(blob.show_bytes(repo, rel))
            cat = blob.sha256_hex(blob.blob_bytes(repo, rel))
            prov = blob.sha256_hex(blob.provenance_bytes(repo / rel, repo=repo))
            assert show == cat == prov, (rel, show, cat, prov)
            checked.append({"path": rel, "git_show_sha256": show,
                            "git_cat_file_sha256": cat,
                            "provenance_sha256": prov,
                            "identical": True})

    print(json.dumps({
        "probe": "probe2-independent-show",
        "unit_id": "IMP-0439",
        "method": "git show <rev>:<path> and git cat-file -p, two fixtures, "
                  "second CRLF rewrite, digests re-derived independently",
        "checked": checked,
        "sentinel": "SENTINEL:IMP-0439:PROVENANCE-BLOB-HASHED",
    }, indent=2))
    print("SUCCESS:IMP-0439-probe2 git show == cat-file == provenance digest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
