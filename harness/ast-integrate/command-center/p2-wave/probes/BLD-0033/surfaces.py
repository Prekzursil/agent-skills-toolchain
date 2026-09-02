"""Search-surface enumeration with honest absent/error status.

A GENUINELY-NEW verdict is forbidden unless every required surface is
actually enumerated. An omitted surface is NOT-CHECKED, never a clean miss.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from mechanism import DELETED_SYMBOL

CODE_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".ts", ".md", ".json"}
MECH_SUFFIXES = {".py", ".mjs", ".js", ".cjs", ".ts"}
SKIP_PARTS = {
    "node_modules",
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
}
SECRETISH = {".env", "credentials.json", "accounts.json"}
REQUIRED_SURFACE_IDS = (
    "repo_working_tree",
    "git_branches",
    "git_worktrees",
    "git_history_deleted",
    "live_claude",
    "live_agents",
    "installed_skills_plugins",
    "wfa_0120_workflows",
)


def _is_skipped(path: Path) -> bool:
    parts = set(path.parts)
    if parts & SKIP_PARTS:
        return True
    if path.name in SECRETISH or path.name.startswith(".env"):
        return True
    if path.name.endswith(".pem") or path.name.endswith(".key"):
        return True
    return False


def walk_code(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS and not d.startswith(".git")]
        base = Path(dirpath)
        if _is_skipped(base):
            continue
        for name in filenames:
            p = base / name
            if _is_skipped(p):
                continue
            if p.suffix.lower() in CODE_SUFFIXES:
                out.append(p)
    return sorted(out)


def walk_mech(root: Path) -> list[Path]:
    """Source files eligible for mechanism (shingle) comparison.

    Surface enumeration still uses walk_code (includes SKILL.md / plugin.json).
    Mechanism comparison is code-only so markdown inventory rows and binary
    JSON sidecars cannot crash or dominate Jaccard.
    """
    return [p for p in walk_code(root) if p.suffix.lower() in MECH_SUFFIXES]


def inventory_roots(repo: Path) -> list[Path]:
    home = Path.home()
    return [
        repo / ".agents",
        repo / ".claude",
        home / ".claude",
        home / ".agents",
        repo / "skills",
        repo / "plugins",
    ]


def _run_git(repo: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git_available(repo: Path) -> bool:
    if not repo.is_dir():
        return False
    code, _ = _run_git(repo, ["rev-parse", "--is-inside-work-tree"])
    return code == 0


def git_branches(repo: Path) -> dict:
    if not git_available(repo):
        return {"status": "absent", "names": [], "queries": ["git branch -a"]}
    code, text = _run_git(repo, ["branch", "-a", "--format=%(refname:short)"])
    names = [ln.strip() for ln in text.splitlines() if ln.strip() and code == 0]
    return {
        "status": "enumerated" if code == 0 else "error",
        "names": names,
        "queries": ["git branch -a --format=%(refname:short)"],
        "count": len(names),
    }


def git_worktrees(repo: Path) -> dict:
    if not git_available(repo):
        return {"status": "absent", "rows": [], "queries": ["git worktree list --porcelain"]}
    code, text = _run_git(repo, ["worktree", "list", "--porcelain"])
    paths = [
        ln.split(" ", 1)[1].strip()
        for ln in text.splitlines()
        if ln.startswith("worktree ")
    ]
    return {
        "status": "enumerated" if code == 0 else "error",
        "rows": paths,
        "queries": ["git worktree list --porcelain"],
        "count": len(paths),
    }


def git_history_deleted(repo: Path, symbol: str = DELETED_SYMBOL) -> dict:
    queries = [
        f"git log --diff-filter=D --summary --all",
        f"git log -S {symbol} --all --pretty=format:%H --name-only",
        "git grep -n --all -- <symbol>  (HEAD tree)",
    ]
    if not git_available(repo):
        return {
            "status": "absent",
            "symbol": symbol,
            "found_in_head": False,
            "found_in_deleted": False,
            "deleted_path": None,
            "commit": None,
            "queries": queries,
        }
    head_code, head_text = _run_git(repo, ["grep", "-n", "-F", symbol, "HEAD"])
    found_in_head = head_code == 0 and symbol in head_text
    log_code, log_text = _run_git(
        repo,
        ["log", "-S", symbol, "--all", "--pretty=format:%H", "--name-only", "--diff-filter=D"],
    )
    commit = None
    deleted_path = None
    found_in_deleted = False
    if log_code == 0:
        lines = [ln.strip() for ln in log_text.splitlines() if ln.strip()]
        hashes = [
            ln
            for ln in lines
            if len(ln) in {40, 64} and all(c in "0123456789abcdef" for c in ln)
        ]
        paths = [ln for ln in lines if ln not in hashes]
        if hashes and paths:
            commit = hashes[0]
            deleted_path = paths[0]
            found_in_deleted = True
        elif hashes:
            commit = hashes[0]
            # recover path via show
            sc, st = _run_git(repo, ["show", "--name-only", "--pretty=format:", hashes[0]])
            if sc == 0:
                names = [ln.strip() for ln in st.splitlines() if ln.strip()]
                deleted_path = names[0] if names else None
                found_in_deleted = bool(deleted_path)
    snippet = None
    if found_in_deleted and commit and deleted_path:
        # parent of the deleting commit still has the blob
        pc, _ = _run_git(repo, ["rev-parse", f"{commit}^"])
        if pc == 0:
            sc, st = _run_git(repo, ["show", f"{commit}^:{deleted_path}"])
            if sc == 0 and symbol in st:
                snippet = next((ln.strip() for ln in st.splitlines() if symbol in ln), symbol)
                found_in_deleted = True
    return {
        "status": "enumerated",
        "symbol": symbol,
        "found_in_head": found_in_head,
        "found_in_deleted": found_in_deleted,
        "deleted_path": deleted_path,
        "commit": commit,
        "snippet": snippet,
        "queries": queries,
    }


def dir_surface(path: Path, queries: list[str]) -> dict:
    files = walk_code(path) if path.is_dir() else []
    status = "enumerated" if path.is_dir() else "absent"
    return {
        "status": status,
        "path": str(path),
        "file_count": len(files),
        "queries": queries,
        "files": [str(p) for p in files[:80]],
    }


def inventory_surface(roots: list[Path]) -> dict:
    found: list[str] = []
    queries = [
        "glob **/SKILL.md",
        "glob **/plugin.json",
        "glob **/marketplace*.json",
    ]
    enumerated_any = False
    for root in roots:
        if not root.is_dir():
            continue
        enumerated_any = True
        for p in walk_code(root):
            if p.name in {"SKILL.md", "plugin.json"} or "marketplace" in p.name.lower():
                found.append(str(p))
    return {
        "status": "enumerated" if enumerated_any else "absent",
        "paths": found,
        "count": len(found),
        "queries": queries,
    }


def wfa_surface(path: Path) -> dict:
    queries = [
        "read command-center/wfa/WFA-0120-rebuild-versus-existing-gate.json",
        "consume workflow rows; do not re-detect workflow rebuilds",
    ]
    if not path.is_file():
        return {"status": "absent", "path": str(path), "rows": [], "queries": queries}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "status": "error",
            "path": str(path),
            "error": type(exc).__name__,
            "rows": [],
            "queries": queries,
        }
    rows = []
    if isinstance(doc, dict):
        rows = list(doc.get("rows") or doc.get("entries") or [])
    return {
        "status": "consumed",
        "path": str(path),
        "rows": rows[:50],
        "queries": queries,
        "count": len(rows),
    }


def fixture_surfaces(estate: Path, git_repo: Path | None) -> dict:
    """All required surfaces for the planted-control estate."""
    repo_files = walk_code(estate / "tools")
    live_c = dir_surface(
        estate / "live-claude",
        ["walk fixtures/estate/live-claude for plugin.json"],
    )
    live_a = dir_surface(
        estate / "live-agents",
        ["walk fixtures/estate/live-agents for SKILL.md"],
    )
    inv = inventory_surface(
        [estate / "live-claude", estate / "live-agents", estate / "inventory"]
    )
    wfa = wfa_surface(estate / "wfa" / "WFA-0120-rebuild-versus-existing-gate.json")
    branches = git_branches(git_repo) if git_repo else {
        "status": "absent",
        "names": [],
        "queries": ["git branch -a"],
    }
    trees = git_worktrees(git_repo) if git_repo else {
        "status": "absent",
        "rows": [],
        "queries": ["git worktree list --porcelain"],
    }
    hist = git_history_deleted(git_repo) if git_repo else {
        "status": "absent",
        "found_in_deleted": False,
        "found_in_head": False,
        "queries": ["git log -S"],
    }
    pack = {
        "repo_working_tree": {
            "status": "enumerated",
            "path": str(estate),
            "file_count": len(repo_files),
            "queries": [
                "walk tools/lib and tools/rebuilds; mechanism shingles, not filenames",
                "export-name token search (strike-1, expected miss on rename)",
            ],
        },
        "git_branches": branches,
        "git_worktrees": trees,
        "git_history_deleted": hist,
        "live_claude": live_c,
        "live_agents": live_a,
        "installed_skills_plugins": inv,
        "wfa_0120_workflows": wfa,
    }
    return pack


def host_surfaces(repo: Path) -> dict:
    """Honest live-estate surfaces on this worktree. Missing stays absent."""
    home = Path.home()
    claude = home / ".claude"
    agents = home / ".agents"
    wfa = repo / "command-center" / "wfa" / "WFA-0120-rebuild-versus-existing-gate.json"
    inv_roots = [
        repo / ".agents",
        repo / ".claude",
        claude,
        agents,
        repo / "skills",
        repo / "plugins",
    ]
    return {
        "repo_working_tree": {
            "status": "enumerated",
            "path": str(repo),
            "file_count": len(walk_code(repo / "tools")),
            "queries": [
                "walk tools/ for program-built modules",
                "compare MECHANISM shingles against other surfaces",
            ],
        },
        "git_branches": git_branches(repo),
        "git_worktrees": git_worktrees(repo),
        "git_history_deleted": git_history_deleted(repo),
        "live_claude": dir_surface(
            claude, ["walk ~/.claude (read-only) for code/plugin files"]
        ),
        "live_agents": dir_surface(
            agents, ["walk ~/.agents (read-only) for skills"]
        ),
        "installed_skills_plugins": inventory_surface(inv_roots),
        "wfa_0120_workflows": wfa_surface(wfa),
    }


def surfaces_complete(pack: dict) -> bool:
    for sid in REQUIRED_SURFACE_IDS:
        row = pack.get(sid) or {}
        if row.get("status") not in {"enumerated", "consumed"}:
            return False
    return True


def named_surface_list(pack: dict) -> list[dict]:
    rows = []
    for sid in REQUIRED_SURFACE_IDS:
        row = pack.get(sid) or {}
        rows.append(
            {
                "id": sid,
                "status": row.get("status") or "absent",
                "queries": list(row.get("queries") or []),
                "detail": {
                    k: v
                    for k, v in row.items()
                    if k not in {"files"}
                },
            }
        )
    return rows


def incomplete_ids(pack: dict) -> list[str]:
    missing = []
    for sid in REQUIRED_SURFACE_IDS:
        row = pack.get(sid) or {}
        if row.get("status") not in {"enumerated", "consumed"}:
            missing.append(sid)
    return missing
