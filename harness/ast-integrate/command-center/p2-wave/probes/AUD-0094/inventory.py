#!/usr/bin/env python3
"""Deleted-path inventory for AUD-0094.

Sources, in order of authority:
  1. git DELETE-ALL / 77-file deletion commit (if this worktree has git)
  2. catalog-named retired filenames (explicit RETIRED markers, not guesses)
  3. planted 77-file / 5-tree control estate (detector proof; not claimed as
     the owner's historical bytes)

Never invent git paths. Catalog-claimed count stays 77 even when git is absent.
"""
from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_CLAIMED_COUNT = 77
PLANTED_PREFIX = "aud0094-retired"
PLANTED_TREES = (
    ("tree-agentbridge", 16),
    ("tree-codex-stub", 16),
    ("tree-tools-a", 15),
    ("tree-tools-b", 15),
    ("tree-harness", 15),
)
CATALOG_NAMED_RETIRED = (
    "CODEX-STUB-RETIREMENT-LANE.md",
)
# Salvage home cited by later units; missing here is not a DELETE-ALL dangling
# reference unless git says the path itself was in the 77.
SALVAGE_HOME_CITED = (
    "tools/lib/net-allowlist.mjs",
    "tools/lib/security.mjs",
    "tools/lib/git-diff.mjs",
    "tools/lib/handled-ledger.mjs",
)
SKIP_DIR_NAMES = frozenset(
    {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}
)
SKIP_SUFFIXES = frozenset({".pyc", ".pyo", ".so", ".bin", ".png", ".jpg", ".woff"})
OUTPUT_REL = "command-center/audit/AUD-0094-retirement-blast-radius.json"


@dataclass(frozen=True)
class DeletedPath:
    path: str
    tree: str
    source: str
    module_name: str | None = None

    def as_row(self) -> dict:
        row = asdict(self)
        return row


def planted_module_name(rel: str) -> str:
    parts = [p.replace("-", "_") for p in Path(rel).with_suffix("").parts]
    return "_".join(parts)


def planted_paths() -> list[DeletedPath]:
    rows: list[DeletedPath] = []
    for tree, count in PLANTED_TREES:
        for i in range(count):
            if tree == "tree-codex-stub" and i == 0:
                name = "file-00.sh"
            elif tree == "tree-tools-b" and i == 0:
                name = "file-00.mjs"
            else:
                name = f"file-{i:02d}.py"
            rel = f"{PLANTED_PREFIX}/{tree}/{name}"
            rows.append(
                DeletedPath(
                    path=rel,
                    tree=tree,
                    source="planted-control",
                    module_name=planted_module_name(rel),
                )
            )
    if len(rows) != CATALOG_CLAIMED_COUNT:
        raise RuntimeError(f"planted inventory is {len(rows)}, want {CATALOG_CLAIMED_COUNT}")
    return rows


def _git(args: list[str], timeout: float = 12.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def git_status() -> dict:
    try:
        p = _git(["rev-parse", "--is-inside-work-tree"], timeout=8.0)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": type(exc).__name__, "paths": []}
    if p.returncode != 0 or (p.stdout or "").strip() != "true":
        err = ((p.stderr or "") + (p.stdout or "")).strip()[:300]
        return {"available": False, "reason": err or "not-a-git-worktree", "paths": []}
    return {"available": True, "reason": "inside-work-tree", "paths": []}


def _deleted_names_for_commit(commit: str) -> list[str]:
    p = _git(
        ["diff-tree", "--no-commit-id", "--name-only", "--diff-filter=D", "-r", commit],
        timeout=15.0,
    )
    if p.returncode != 0:
        return []
    return sorted({ln.strip().replace("\\", "/") for ln in p.stdout.splitlines() if ln.strip()})


def recover_git_delete_all() -> dict:
    base = git_status()
    if not base["available"]:
        return {**base, "commit": None, "paths": [], "method": "none"}
    commits: list[tuple[str, str]] = []
    try:
        grepped = _git(
            ["log", "--all", "--grep=DELETE-ALL", "--pretty=format:%H%x09%s"],
            timeout=15.0,
        )
        if grepped.returncode == 0:
            for line in grepped.stdout.splitlines():
                if "\t" in line:
                    cid, subj = line.split("\t", 1)
                    commits.append((cid.strip(), subj.strip()))
        stat = _git(
            ["log", "--all", "--pretty=format:COMMIT %H %s", "--shortstat"],
            timeout=15.0,
        )
        if stat.returncode == 0:
            current_c = ""
            current_s = ""
            for line in stat.stdout.splitlines():
                if line.startswith("COMMIT "):
                    rest = line[len("COMMIT ") :]
                    parts = rest.split(" ", 1)
                    current_c = parts[0]
                    current_s = parts[1] if len(parts) > 1 else ""
                elif "77 files changed" in line and current_c:
                    commits.append((current_c, current_s or line.strip()))
    except subprocess.TimeoutExpired:
        return {
            "available": True,
            "reason": "git-log-timeout",
            "commit": None,
            "paths": [],
            "method": "timeout",
        }
    seen: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for cid, subj in commits:
        if cid not in seen:
            seen.add(cid)
            ordered.append((cid, subj))
    best: tuple[str, str, list[str]] | None = None
    for cid, subj in ordered[:12]:
        names = _deleted_names_for_commit(cid)
        if not names:
            continue
        if len(names) == CATALOG_CLAIMED_COUNT:
            best = (cid, subj, names)
            break
        if best is None or abs(len(names) - CATALOG_CLAIMED_COUNT) < abs(
            len(best[2]) - CATALOG_CLAIMED_COUNT
        ):
            best = (cid, subj, names)
    if best is None:
        return {
            "available": True,
            "reason": "no-delete-all-commit",
            "commit": None,
            "paths": [],
            "method": "git-log-grep-and-shortstat",
        }
    cid, subj, names = best
    return {
        "available": True,
        "reason": "ok",
        "commit": cid,
        "subject": subj,
        "paths": names,
        "method": "git-diff-tree-deleted",
        "count": len(names),
    }


def git_deleted_rows(git_info: dict) -> list[DeletedPath]:
    rows: list[DeletedPath] = []
    for rel in git_info.get("paths") or []:
        rel = str(rel).replace("\\", "/")
        tree = rel.split("/", 1)[0] if "/" in rel else "root"
        rows.append(DeletedPath(path=rel, tree=tree, source="git", module_name=None))
    return rows


def catalog_named_rows() -> list[DeletedPath]:
    rows: list[DeletedPath] = []
    for rel in CATALOG_NAMED_RETIRED:
        rows.append(
            DeletedPath(path=rel, tree="catalog-named", source="catalog-named", module_name=None)
        )
    return rows


def load_inventory() -> dict:
    planted = planted_paths()
    git_info = recover_git_delete_all()
    git_rows = git_deleted_rows(git_info)
    named = catalog_named_rows()
    by_path: dict[str, DeletedPath] = {}
    for row in [*git_rows, *named, *planted]:
        by_path.setdefault(row.path, row)
    trees = sorted({r.tree for r in by_path.values()})
    return {
        "catalog_claimed_count": CATALOG_CLAIMED_COUNT,
        "git": {
            "available": bool(git_info.get("available")),
            "reason": git_info.get("reason"),
            "commit": git_info.get("commit"),
            "subject": git_info.get("subject"),
            "method": git_info.get("method"),
            "recovered_count": len(git_rows),
        },
        "recovered_count": len(git_rows),
        "catalog_named_count": len(named),
        "planted_count": len(planted),
        "tree_count": 5,
        "trees": trees,
        "paths": [r.as_row() for r in by_path.values()],
        "objects": list(by_path.values()),
        "salvage_home_cited": list(SALVAGE_HOME_CITED),
        "salvage_home_present": {
            p: (REPO / p).is_file() for p in SALVAGE_HOME_CITED
        },
    }


def iter_surviving_files(root: Path | None = None):
    root = root or REPO
    out = (REPO / OUTPUT_REL).resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in SKIP_DIR_NAMES for part in rel_parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if path.resolve() == out:
                continue
        except OSError:
            pass
        yield path
