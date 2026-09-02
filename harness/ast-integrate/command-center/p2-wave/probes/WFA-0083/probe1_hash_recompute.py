#!/usr/bin/env python3
"""Named probe 1: committed-blob hash + ghost/orphan reconciliation.

Signal 1: after the worktree is dirtied, recompute still matches the snapshot
and differs from a worktree hash. Signal 2: a manifest row with no file, and
a file with no row, are both failures and both reported.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    OUT_REL,
    BlobStore,
    prove_blob_not_worktree,
    prove_ghost_and_orphan,
)

ART = REPO / OUT_REL


def _fail(msg: str, extra=None) -> int:
    print(f"FAILED:WFA-0083-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("AuditReport missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0083":
        return _fail("unit_id", doc.get("unit_id"))
    if "SUCCESS:WFA-0083" not in json.dumps(doc):
        return _fail("sentinel absent")

    blob = prove_blob_not_worktree()
    if not blob.get("ok"):
        return _fail("blob-not-worktree control did not fire", blob)
    git = blob.get("git") or {}
    store = blob.get("blob_store") or {}
    if git.get("blob") == git.get("worktree"):
        return _fail("git blob hash equalled dirtied worktree", git)
    if store.get("recomputed") == store.get("worktree"):
        return _fail("blob-store hash equalled dirtied worktree", store)

    recon = prove_ghost_and_orphan()
    if not recon.get("ok"):
        return _fail("ghost/orphan control did not fire", recon)
    ghost = recon["ghost"]["missing_file"]
    orphan = recon["orphan"]["orphan_file"]
    if "ghost.json" not in ghost:
        return _fail("ghost.json not reported as missing_file", recon)
    if "orphan.json" not in orphan:
        return _fail("orphan.json not reported as orphan_file", recon)
    if recon["ghost"]["ok"] or recon["orphan"]["ok"]:
        return _fail("ghost or orphan was green", recon)

    live = BlobStore(REPO)
    sha, n, src = live.recompute(OUT_REL)
    worktree = hashlib.sha256(ART.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    # Live file was just registered: blob and worktree should still match.
    # The control above already proved they DIVERGE after a dirty write.
    if sha != worktree:
        return _fail(
            "live AuditReport blob/worktree diverge before any dirtying",
            {"blob": sha, "worktree": worktree, "source": src, "bytes": n},
        )

    print(
        json.dumps(
            {
                "probe": "probe1-hash-recompute",
                "unit_id": "WFA-0083",
                "pass": True,
                "git_blob_ne_worktree": git.get("blob") != git.get("worktree"),
                "store_blob_ne_worktree": store.get("recomputed") != store.get("worktree"),
                "ghost_reported": ghost,
                "orphan_reported": orphan,
                "live_hash_source": src,
                "live_sha256": sha,
            },
            indent=2,
        )
    )
    print("SUCCESS:WFA-0083-probe1 committed-blob hash and ghost/orphan both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
