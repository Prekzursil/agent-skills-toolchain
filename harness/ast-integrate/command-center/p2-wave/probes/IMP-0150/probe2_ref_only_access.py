#!/usr/bin/env python3
"""Probe 2: ref-only path records git show <ref>:<path> and reads back."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from discovery.local_repo import (  # noqa: E402
    ArchiveForbidden,
    discover_local,
    fetch_bytes,
    find_path,
    git_bytes,
    sha256_bytes,
)
from scenario import REF_ONLY, REF_ONLY_REF, plant_repo  # noqa: E402


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="imp0150-p2-") as td:
        tmp = Path(td)
        home = tmp / "home"
        home.mkdir()
        planted = plant_repo(tmp / "repo", home, tmp / "linked")
        root = planted["root"]

        wt_only = discover_local(root, include_refs=False, include_linked_worktrees=False)
        full = discover_local(root, include_refs=True, include_linked_worktrees=True)

        bare = root / REF_ONLY
        if bare.is_file():
            failures.append("ref-only file is still in the primary worktree")

        wt_hits = find_path(wt_only, REF_ONLY)
        if wt_hits:
            failures.append("worktree-only scan found ref-only path (should miss)")

        ref_hits = find_path(full, REF_ONLY)
        if len(ref_hits) != 1:
            failures.append(f"expected 1 ref-only row, got {len(ref_hits)}")
            payload = {
                "failures": failures,
                "full_paths": [c.path for c in full],
                "pass": False,
                "probe": "probe2-ref-only-access",
                "unit_id": "IMP-0150",
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            print("FAILED:IMP-0150-probe2 ref-only row missing")
            return 1

        row = ref_hits[0]
        want_access = planted["ref_only_access"]
        if row.access_method != want_access:
            failures.append(
                f"access_method {row.access_method!r} != {want_access!r}"
            )
        if not row.access_method.startswith("git show "):
            failures.append("ref-only access_method is not git show")
        if "archive" in row.access_method:
            failures.append("access_method names git archive")
        if row.location != "ref":
            failures.append(f"location={row.location!r} want ref")
        if row.ref != REF_ONLY_REF:
            failures.append(f"ref={row.ref!r} want {REF_ONLY_REF}")

        independent = git_bytes(root, "show", f"{REF_ONLY_REF}:{REF_ONLY}")
        via = fetch_bytes(root, row.access_method)
        if via != independent:
            failures.append("read-back bytes != git show bytes")
        got_hash = sha256_bytes(via)
        if got_hash != planted["ref_only_hash"] or got_hash != row.content_hash:
            failures.append(
                f"hash mismatch independent={sha256_bytes(independent)} "
                f"row={row.content_hash} planted={planted['ref_only_hash']}"
            )

        # Bare path is unreadable — that is why git show is recorded.
        bare_unreadable = not bare.is_file()
        try:
            fetch_bytes(root, REF_ONLY)
            bare_read_ok = True
        except (OSError, FileNotFoundError):
            bare_read_ok = False
        if not bare_unreadable or bare_read_ok:
            failures.append("bare path was readable; fixture is not ref-only")

        linked_hits = [
            c
            for c in full
            if c.path == planted["linked_path"] and c.location == "linked-worktree"
        ]
        if not linked_hits:
            failures.append("linked worktree workflow not discovered")
        else:
            lrow = linked_hits[0]
            lvia = fetch_bytes(root, lrow.access_method)
            if sha256_bytes(lvia) != planted["linked_hash"]:
                failures.append("linked worktree read-back hash mismatch")
            if lrow.access_method.startswith("git show "):
                failures.append("linked worktree file should be filesystem-readable")

        archive_guard = False
        try:
            git_bytes(root, "archive", "HEAD")
        except ArchiveForbidden:
            archive_guard = True
        except RuntimeError:
            archive_guard = False
        if not archive_guard:
            failures.append("git archive was not forbidden")

        payload = {
            "access_method": row.access_method,
            "archive_forbidden": archive_guard,
            "bare_path_unreadable": bare_unreadable,
            "content_hash": row.content_hash,
            "failures": failures,
            "linked_worktree_found": bool(linked_hits),
            "pass": not failures,
            "probe": "probe2-ref-only-access",
            "read_back_hash": got_hash,
            "ref": row.ref,
            "unit_id": "IMP-0150",
            "worktree_only_hits": len(wt_hits),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if failures:
            print("FAILED:IMP-0150-probe2 " + "; ".join(failures))
            return 1
        print(
            "SUCCESS:IMP-0150-probe2 ref-only access_method git show; "
            "read-back hash matches"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
