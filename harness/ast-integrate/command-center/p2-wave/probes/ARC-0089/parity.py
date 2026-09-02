"""Three-way skill-tree parity: repo vs both live trees.

Keyed on package id (the directory that contains SKILL.md). Two signals
per id: sha256 of SKILL.md bytes, and byte size. Host live trees are
probed; on this Linux worktree they are expected to be absent, so the
contract is exercised on fixtures that encode the named failure class
(skill in repo, missing from a live tree).
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def skill_index(tree: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not tree.is_dir():
        return out
    for skill_md in sorted(tree.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        sid = skill_md.parent.name
        sha, size = digest_file(skill_md)
        rel = skill_md.relative_to(tree).as_posix()
        out[sid] = {
            "id": sid,
            "rel": rel,
            "sha256": sha,
            "bytes": size,
            "path": str(skill_md),
        }
    return out


def host_skill_trees() -> list[dict[str, Any]]:
    candidates = [
        Path.home() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".claude" / "skills",
        Path.home() / ".agents" / "skills",
        REPO / "skills",
        REPO / ".claude" / "skills",
        REPO / ".cursor" / "skills",
        REPO / ".agents" / "skills",
    ]
    rows = []
    seen: set[str] = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        n = 0
        if p.is_dir():
            n = sum(1 for q in p.rglob("SKILL.md") if q.is_file())
        rows.append(
            {
                "path": key,
                "exists": p.exists(),
                "is_dir": p.is_dir(),
                "skill_md_count": n,
            }
        )
    return rows


def three_way(
    repo: Path, live_claude: Path, live_agents: Path
) -> dict[str, Any]:
    r = skill_index(repo)
    c = skill_index(live_claude)
    a = skill_index(live_agents)
    ids = sorted(set(r) | set(c) | set(a))
    repo_not_live_claude = sorted(set(r) - set(c))
    repo_not_live_agents = sorted(set(r) - set(a))
    live_claude_not_repo = sorted(set(c) - set(r))
    live_agents_not_repo = sorted(set(a) - set(r))
    live_claude_not_live_agents = sorted(set(c) - set(a))
    live_agents_not_live_claude = sorted(set(a) - set(c))
    hash_mismatch = []
    identical = []
    for sid in ids:
        present_in = [name for name, idx in (("repo", r), ("live_claude", c), ("live_agents", a)) if sid in idx]
        shas = {name: idx[sid]["sha256"] for name, idx in (("repo", r), ("live_claude", c), ("live_agents", a)) if sid in idx}
        sizes = {name: idx[sid]["bytes"] for name, idx in (("repo", r), ("live_claude", c), ("live_agents", a)) if sid in idx}
        if len(present_in) == 3 and len(set(shas.values())) == 1:
            identical.append(sid)
        elif len(set(shas.values())) > 1:
            hash_mismatch.append(
                {
                    "id": sid,
                    "present_in": present_in,
                    "sha256": shas,
                    "bytes": sizes,
                }
            )
    difference_set = {
        "repo_not_in_live_claude": repo_not_live_claude,
        "repo_not_in_live_agents": repo_not_live_agents,
        "live_claude_not_in_repo": live_claude_not_repo,
        "live_agents_not_in_repo": live_agents_not_repo,
        "live_claude_not_in_live_agents": live_claude_not_live_agents,
        "live_agents_not_in_live_claude": live_agents_not_live_claude,
        "hash_mismatch": hash_mismatch,
    }
    parity_ok = (
        not repo_not_live_claude
        and not repo_not_live_agents
        and not live_claude_not_repo
        and not live_agents_not_repo
        and not live_claude_not_live_agents
        and not live_agents_not_live_claude
        and not hash_mismatch
    )
    return {
        "kind": "deploy-parity-census",
        "trees": {
            "repo": str(repo),
            "live_claude": str(live_claude),
            "live_agents": str(live_agents),
        },
        "ids": {
            "repo": sorted(r),
            "live_claude": sorted(c),
            "live_agents": sorted(a),
            "union": ids,
        },
        "identical": identical,
        "difference_set": difference_set,
        "parity_ok": parity_ok,
        "failure_class_repo_not_in_live": bool(
            repo_not_live_claude or repo_not_live_agents
        ),
        "signals": ["sha256", "byte-size"],
    }
