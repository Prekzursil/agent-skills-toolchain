#!/usr/bin/env python3
"""Probe 2: CRLF-normalise then hash the git blob, never git archive.

Mechanically different from probe 1 (set difference). A dirty CRLF worktree
must not be declared a hash mismatch against an LF blob. `git archive` is
measured and refused as the authority.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from engine import RecipeError, UNIT, probe2_payload, refuse_archive_recipe  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    try:
        refuse_archive_recipe("git archive | tar -x")
        return fail("refuse_archive_recipe did not raise")
    except RecipeError:
        pass

    payload = probe2_payload()
    print(json.dumps(payload, sort_keys=True))
    if payload["hash_authority"] != "git cat-file -p":
        return fail(f"authority={payload['hash_authority']}")
    if payload["archive_used_as_authority"] is not False:
        return fail("git archive was used as the hash authority")
    if not payload["archive_recipe_refused"]:
        return fail("archive recipe was not refused")
    if not payload["blob_equals_lf"]:
        return fail("cat-file blob is not the planted LF bytes")
    if payload["blob_equals_worktree"]:
        return fail("blob equals CRLF worktree; fixture did not plant the trap")
    if not payload["worktree_is_crlf"]:
        return fail("worktree is not CRLF")
    if payload["blob_crlf_count"] != 0:
        return fail(f"blob crlf_count={payload['blob_crlf_count']}")
    if payload["worktree_crlf_count"] < 1:
        return fail("worktree has no CRLF")
    if not payload["worktree_raw_would_false_mismatch"]:
        return fail("raw worktree hash did not diverge from the blob")
    if not payload["crlf_normalized_matches_blob"]:
        return fail("CRLF-normalised worktree did not match the blob")
    if payload["blob_sha256"] == payload["worktree_raw_sha256"]:
        return fail("blob and raw worktree hashes collided")
    if not payload["pass"]:
        return fail("probe2 conjunction failed")
    print(
        f"authority=git-cat-file-p blob={payload['blob_bytes']}B/0CRLF "
        f"worktree={payload['worktree_raw_bytes']}B/"
        f"{payload['worktree_crlf_count']}CRLF "
        f"archive_equals_blob={payload['archive_equals_blob']}"
    )
    print("SUCCESS:ADV-0111-probe2 blob-not-archive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
