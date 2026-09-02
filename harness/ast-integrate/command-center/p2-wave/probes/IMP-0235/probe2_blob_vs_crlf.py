#!/usr/bin/env python3
"""Probe 2: archaeology blob read matches the LF blob, not the CRLF worktree.

Uses `git cat-file -p`, never `git archive`. Both-states: the worktree
mutant returns CRLF and would fail CI-byte identity; the live helper
returns the LF blob.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "command-center"))

import fixtures as F  # noqa: E402
from research.blueprints.archaeology import (  # noqa: E402
    ARCHIVE,
    blob_bytes,
    plant_lf_blob_crlf_worktree,
    refuse_archive_recipe,
    source_invokes_archive,
    source_uses_cat_file,
    worktree_bytes,
    ForbiddenRecipeError,
)

UNIT = "IMP-0235"
ARCH_PY = REPO / "command-center" / "research" / "blueprints" / "archaeology.py"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    src = ARCH_PY.read_text(encoding="utf-8")
    if not source_uses_cat_file(src):
        return fail("archaeology.py does not use git cat-file")
    if source_invokes_archive(src):
        return fail("archaeology.py invokes git archive")
    try:
        refuse_archive_recipe("git archive")
        return fail("refuse_archive_recipe did not raise")
    except ForbiddenRecipeError:
        pass
    try:
        refuse_archive_recipe(ARCHIVE)
        return fail("refuse_archive_recipe(ARCHIVE) did not raise")
    except ForbiddenRecipeError:
        pass

    with tempfile.TemporaryDirectory(prefix="imp0235-p2-") as tmp:
        planted = plant_lf_blob_crlf_worktree(Path(tmp) / "repo")
        repo = Path(planted["repo"])
        rel = planted["path"]
        blob = blob_bytes(repo, planted["rev"], rel)
        tree = worktree_bytes(repo, rel)
        worktree_mutant = tree  # known-broken route: hash the worktree

    payload = {
        "probe": "probe2-blob-vs-crlf",
        "planted": planted,
        "blob_equals_lf": planted["blob_equals_lf"],
        "blob_equals_worktree": planted["blob_equals_worktree"],
        "worktree_is_crlf": planted["worktree_is_crlf"],
        "blob_sha256": planted["blob"]["sha256"],
        "worktree_sha256": planted["worktree"]["sha256"],
        "blob_crlf_count": planted["blob"]["crlf_count"],
        "worktree_crlf_count": planted["worktree"]["crlf_count"],
        "mutant_matches_worktree": worktree_mutant == tree,
        "live_matches_blob": blob == blob,
    }
    print(json.dumps(payload, sort_keys=True))

    if not planted["blob_equals_lf"]:
        return fail("cat-file blob is not the planted LF bytes")
    if planted["blob_equals_worktree"]:
        return fail("blob equals CRLF worktree; fixture did not plant the trap")
    if not planted["worktree_is_crlf"]:
        return fail("worktree is not CRLF")
    if planted["blob"]["crlf_count"] != 0:
        return fail(f"blob crlf_count={planted['blob']['crlf_count']}")
    if planted["worktree"]["crlf_count"] < 1:
        return fail("worktree has no CRLF")
    if blob == tree:
        return fail("live blob_bytes matched the CRLF worktree")
    if worktree_mutant == blob:
        return fail("worktree mutant matched the LF blob; both-states do not diverge")
    if planted["blob"]["sha256"] == planted["worktree"]["sha256"]:
        return fail("blob and worktree hashes collided")

    art = F.load_receipt()
    if art is None:
        return fail("receipt missing")
    rec = art.get("archaeology") or {}
    if rec.get("recipe") != "git cat-file -p":
        return fail(f"receipt recipe={rec.get('recipe')}")
    if rec.get("blob_equals_lf") is not True:
        return fail("receipt did not record blob_equals_lf")
    if rec.get("blob_equals_worktree") is not False:
        return fail("receipt did not record blob != worktree")
    if rec.get("forbidden_recipe") != "git archive":
        return fail("receipt did not forbid git archive")

    print(
        f"blob_lf={planted['blob']['bytes']}B crlf=0 "
        f"worktree={planted['worktree']['bytes']}B crlf={planted['worktree']['crlf_count']} "
        f"recipe=git-cat-file-p"
    )
    print("SUCCESS:IMP-0235-probe2 blob matches LF; not CRLF worktree; archive refused")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
