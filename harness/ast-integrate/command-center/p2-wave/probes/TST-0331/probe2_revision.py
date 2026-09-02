#!/usr/bin/env python3
"""Probe 2: cited-revision line checks read git blobs, not HEAD/worktree."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import validator as V  # noqa: E402

UNIT = "TST-0331"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def naive_worktree_read(repo: Path, rel: str, line: int, snippet: str) -> bool:
    """Control: a reader that ignores revision and opens the worktree."""
    path = repo / rel
    if not path.is_file():
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False
    return snippet in lines[line - 1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0331-p2-") as td:
        info = F.build_revision_repo(Path(td))
        repo = Path(info["repo"])
        sha_tall = info["sha_tall"]
        sha_head = info["sha_head"]
        rel = info["path"]
        line = int(info["line"])
        snippet = info["snippet"]
        wt_n = int(info["worktree_lines"])
        if wt_n != 5:
            return fail(f"worktree not truncated: lines={wt_n}")
        if sha_tall == sha_head:
            return fail("tall and HEAD shas are identical")
        if naive_worktree_read(repo, rel, line, snippet):
            return fail("naive worktree reader unexpectedly found tall snippet")

        ctx = V.ResolveContext(root=repo, git_cwd=repo)
        tall = V.Anchor(
            kind=V.KIND_FILE_LINE,
            raw=f"{rel}:{line}@{sha_tall}",
            source="probe2",
            index=0,
            path=rel,
            line=line,
            revision=sha_tall,
            snippet=snippet,
        )
        head = V.Anchor(
            kind=V.KIND_FILE_LINE,
            raw=f"{rel}:{line}@{sha_head}",
            source="probe2",
            index=1,
            path=rel,
            line=line,
            revision=sha_head,
            snippet=snippet,
        )
        unpinned = V.Anchor(
            kind=V.KIND_FILE_LINE,
            raw=f"{rel}:{line}",
            source="probe2",
            index=2,
            path=rel,
            line=line,
            snippet=snippet,
        )
        r_tall = V.resolve_anchor(tall, ctx)
        r_head = V.resolve_anchor(head, ctx)
        r_wt = V.resolve_anchor(unpinned, ctx)
        payload = {
            "pass": r_tall.status == V.RESOLVED
            and r_head.status == V.UNRESOLVED
            and r_wt.status == V.UNRESOLVED,
            "probe": "probe2-revision",
            "unit_id": UNIT,
            "sha_tall": sha_tall,
            "sha_head": sha_head,
            "worktree_lines": wt_n,
            "naive_worktree_would_pass": False,
            "cited_revision": r_tall.as_dict(),
            "head_revision": r_head.as_dict(),
            "unpinned_worktree": r_wt.as_dict(),
        }
        print(json.dumps(payload, sort_keys=True))
        if r_tall.status != V.RESOLVED:
            return fail(f"cited tall revision did not resolve: {r_tall.reason}")
        if r_head.status != V.UNRESOLVED:
            return fail(f"HEAD revision unexpectedly resolved: {r_head.reason}")
        if r_wt.status != V.UNRESOLVED:
            return fail(f"unpinned worktree unexpectedly resolved: {r_wt.reason}")
        if "git-show" not in r_tall.reason:
            return fail(f"tall resolve did not use git-show: {r_tall.reason}")
        print(
            f"cited_rev=RESOLVED head=UNRESOLVED worktree=UNRESOLVED "
            f"naive_worktree=False n_head={wt_n}"
        )
        print(
            f"SUCCESS:{UNIT}-probe2 anchor valid at cited commit and stale at HEAD "
            "resolves via git blob, not worktree"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
