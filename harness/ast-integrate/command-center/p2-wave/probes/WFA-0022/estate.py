#!/usr/bin/env python3
"""Estate inventory for WFA-0022: abandoned families on THIS worktree."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from engine import (
    PRESERVED,
    REPO,
    digest_file,
    git_present,
    judge,
    live_search,
    recover_path,
    sha256_lf,
)

NEEDS_OWNER_TREES = (
    "agent-skills-toolchain",
    "ast-harness-reconcile",
    "ast-statusline-capture",
    "cookie-bridge-skill",
    "ast-increment1",
)

NAMED_ABSENCES = (
    "tools/lib/workspace.mjs",
    "tools/lib/net-allowlist.mjs",
    "command-center/wfa/schema/wfa-schema-pack.json",
    "command-center/ROLLBACK-MANIFEST.md",
    "OWNER-DECISIONS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/24-REPO-RECONCILE.md",
)

SALVAGE_HOME = "tools/lib"
WORKFLOW_ROOTS = (
    "tools/workflow_foundry",
    "tools/worktree_shard",
)

DOES = {
    "handled-ledger.mjs": "lossless uint64 ledger for workflow/event ids",
    "handled-ledger.schema.json": "schema bounding seq to MAX_SAFE_INTEGER",
    "workspace.py": "cross-session worktree write containment",
    "sink_scrub.py": "secret-scrub sink for workflow logs",
    "security.mjs": "JS twin of the secret-scrub sink",
    "observability.py": "observability helper that must pass through the sink",
    "secret_shapes.py": "secret shape catalogue for the scrubber",
    "static_scan.py": "static scan of scrub call sites",
    "provisioner.py": "disposable worktree provisioner; teardown needs content proof",
    "generate.py": "workflow foundry generator (from-trace / from-gap)",
    "replay.py": "workflow replay equality",
    "gap_finder.py": "taxonomy gap finder for workflow import",
}


def _does(path: Path) -> str:
    return DOES.get(path.name, f"salvage file {path.as_posix()}")


def _live_roots() -> list[Path]:
    roots = [REPO / "tools", REPO / "command-center", REPO / ".github"]
    for name in ("skills", "rules", "scripts", "hooks"):
        p = REPO / name
        if p.is_dir():
            roots.append(p)
    return [p for p in roots if p.exists()]


def _iter_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            out.append(p)
    return sorted(out)


def scan_estate() -> dict[str, Any]:
    git_ok = git_present(REPO)
    items: list[dict[str, Any]] = []
    salvage_files = _iter_files(REPO / SALVAGE_HOME)
    roots = _live_roots()

    for path in salvage_files:
        rel = path.relative_to(REPO).as_posix()
        sha, n = digest_file(path)
        git = recover_path(REPO, rel)
        hits = live_search([REPO / SALVAGE_HOME], sha)
        items.append(
            judge(
                item_id=f"delete-all-salvage-{path.name}",
                kind="delete-all-salvage-home",
                path=rel,
                git=git,
                live_hits=hits,
                salvage_worthy=True,
                does=_does(path),
            )
        )

    for rel_root in WORKFLOW_ROOTS:
        for path in _iter_files(REPO / rel_root):
            if path.suffix not in {".py", ".json", ".md"}:
                continue
            rel = path.relative_to(REPO).as_posix()
            sha, _n = digest_file(path)
            git = recover_path(REPO, rel)
            hits = live_search([REPO / rel_root], sha)
            items.append(
                judge(
                    item_id=f"workflow-mech-{path.stem}",
                    kind="workflow-mechanism-live",
                    path=rel,
                    git=git,
                    live_hits=hits,
                    salvage_worthy=path.name
                    in {
                        "generate.py",
                        "replay.py",
                        "gap_finder.py",
                        "provisioner.py",
                        "__init__.py",
                    },
                    does=_does(path),
                )
            )

    for rel in NAMED_ABSENCES:
        live_path = REPO / rel if not rel.startswith("C:") else Path(rel)
        git = recover_path(REPO, rel)
        if git.ok and git.sha256:
            hits = live_search(roots, git.sha256)
        elif live_path.is_file():
            hits = [
                {
                    "path": live_path.as_posix(),
                    "sha256": sha256_lf(live_path.read_bytes()),
                    "bytes": live_path.stat().st_size,
                }
            ]
        else:
            hits = []
        items.append(
            judge(
                item_id=f"named-absence-{Path(rel).name}",
                kind="named-abandoned-input",
                path=rel,
                git=git,
                live_hits=hits,
                salvage_worthy=False,
                does="catalog-named abandoned or missing input",
            )
        )

    for name in NEEDS_OWNER_TREES:
        matches = []
        for base in (REPO, REPO / "tools", REPO / "command-center"):
            if not base.exists():
                continue
            hit = base / name
            if hit.exists():
                matches.append(hit.as_posix())
        git = recover_path(REPO, name)
        live_hits = (
            [{"path": m, "sha256": None, "bytes": 0} for m in matches] if matches else []
        )
        # Directory name hits are not byte identity. Re-classify via judge only
        # when git recovered bytes; otherwise path presence is UNPROVEN or a
        # name-only live hit that must not count as preservation.
        if git.ok and git.sha256:
            hits = live_search(roots, git.sha256)
        else:
            hits = []
        row = judge(
            item_id=f"worktree-{name}",
            kind="removed-or-graded-worktree",
            path=name,
            git=git,
            live_hits=hits,
            mentions=matches,
            salvage_worthy=False,
            does="NEEDS-OWNER-DECISION worktree named by WFA-0015",
        )
        row["name_matches_not_byte_proof"] = matches
        items.append(row)

    items.append(
        judge(
            item_id="removed-worktrees-unnamed-14",
            kind="removed-worktree-family",
            path="(14 worktrees removed in 20-to-6 cleanup; names not on this tree)",
            git=recover_path(REPO, "nonexistent/wfa-0022-removed-worktree"),
            live_hits=[],
            salvage_worthy=False,
            does="family of 14 removed worktrees; identity unrecovered without reflog",
        )
    )
    items.append(
        judge(
            item_id="dead-branches",
            kind="dead-branch",
            path="refs/heads/* (dead branches)",
            git=recover_path(REPO, "refs/heads/nonexistent-wfa-0022-dead"),
            live_hits=[],
            salvage_worthy=False,
            does="dead branches require git for-each-ref; object store absent",
        )
    )
    items.append(
        judge(
            item_id="closed-unmerged-prs",
            kind="closed-pr",
            path="closed-unmerged PR head refs",
            git=recover_path(REPO, "refs/pull/nonexistent/head"),
            live_hits=[],
            salvage_worthy=False,
            does="closed-unmerged PR heads require git refs or API dumps",
        )
    )
    items.append(
        judge(
            item_id="delete-all-77-path-list",
            kind="delete-all-inventory",
            path="(77-file DELETE-ALL path list)",
            git=recover_path(REPO, "DELETE-ALL-77-PATH-LIST"),
            live_hits=[],
            salvage_worthy=False,
            does="authoritative 77-path list and git history absent on this worktree",
        )
    )

    preserved = [i for i in items if i["classification"] == PRESERVED]
    lost = [i for i in items if i["classification"] == "CONTENT-LOST"]
    unproven = [i for i in items if i["classification"] == "UNPROVEN-LOST"]
    candidates = [i["candidate"] for i in items if i.get("candidate")]
    return {
        "git_object_store_present": git_ok,
        "salvage_home": SALVAGE_HOME,
        "salvage_file_count": len(salvage_files),
        "items": items,
        "counts": {
            "items": len(items),
            PRESERVED: len(preserved),
            "CONTENT-LOST": len(lost),
            "UNPROVEN-LOST": len(unproven),
            "candidates_reentered": len(candidates),
        },
        "candidates_reentered": candidates,
        "note": (
            "CONTENT-LOST is not claimed for estate rows when git object "
            "storage is absent: LOST requires both surfaces. Live tools/lib "
            "bytes are CONTENT-PRESERVED-ELSEWHERE at their named paths."
        ),
    }
