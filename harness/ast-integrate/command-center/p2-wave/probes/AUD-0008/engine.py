#!/usr/bin/env python3
"""AUD-0008 detectors: ancestor invariant vs path-surface authorship corroboration.

Probe 1 and probe 2 are mechanically different instruments:
  probe 1 uses `git merge-base --is-ancestor` (never HEAD==pinned-SHA equality)
  probe 2 uses `git diff-tree --name-only` matched against catalog unit ids
Author/committer strings are recorded as forgeable labels only.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PINNED_BASELINE = "53c37c6c"
SENTINEL = (
    "SUCCESS:AUD-0008 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
UNIT_RE = re.compile(r"\b([A-Z]{2,5}-\d{4})\b")
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "dist",
    "build",
    ".tox",
}


def git(
    repo: Path,
    *args: str,
    extra_env: dict[str, str] | None = None,
    timeout: int = 60,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "EMAIL": "aud-0008@invalid.test",
        }
    )
    if extra_env:
        env.update(extra_env)
    cmd = [
        "git",
        "-C",
        str(repo),
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "user.name=AUD-0008",
        "-c",
        "user.email=aud-0008@invalid.test",
        *args,
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def is_git_repo(path: Path) -> bool:
    proc = git(path, "rev-parse", "--is-inside-work-tree")
    return proc.returncode == 0 and (proc.stdout or "").strip() == "true"


def merge_base_is_ancestor(
    repo: Path, ancestor: str, descendant: str = "HEAD"
) -> dict[str, Any]:
    """History-rewrite half. git exit 0 means ancestor IS an ancestor of descendant.

    Deliberately not `rev-parse HEAD == ancestor`. Equality is the forbidden
    expression of the invariant (catalog tests_required).
    """
    proc = git(repo, "merge-base", "--is-ancestor", ancestor, descendant)
    head = git(repo, "rev-parse", descendant)
    anc = git(repo, "rev-parse", "--verify", ancestor)
    head_sha = (head.stdout or "").strip()
    anc_sha = (anc.stdout or "").strip()
    equality = bool(head_sha and anc_sha and head_sha == anc_sha)
    return {
        "instrument": "git merge-base --is-ancestor",
        "ancestor_spec": ancestor,
        "descendant_spec": descendant,
        "ancestor_resolved": anc_sha or None,
        "descendant_resolved": head_sha or None,
        "git_exit_code": proc.returncode,
        "is_ancestor": proc.returncode == 0,
        "baseline_object_missing": anc.returncode != 0,
        "head_equals_baseline": equality,
        "stderr_tail": (proc.stderr or "").strip()[-400:],
    }


def equality_strawman(repo: Path, pinned: str, head: str = "HEAD") -> bool:
    """The detector the catalog forbids. Used only as a negative control."""
    h = git(repo, "rev-parse", head)
    a = git(repo, "rev-parse", "--verify", pinned)
    return bool(
        h.returncode == 0
        and a.returncode == 0
        and (h.stdout or "").strip() == (a.stdout or "").strip()
    )


def load_unit_ids() -> set[str]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    out: set[str] = set()
    for row in data.get("work_units") or []:
        if isinstance(row, dict):
            uid = str(row.get("id") or "")
            if UNIT_RE.fullmatch(uid):
                out.add(uid)
    return out


def classify_paths(paths: list[str], unit_ids: set[str]) -> dict[str, Any]:
    found: set[str] = set()
    probe_hits: list[str] = []
    for path in paths:
        norm = path.replace("\\", "/")
        for match in UNIT_RE.findall(norm):
            if match in unit_ids:
                found.add(match)
        if "/p2-wave/probes/" in f"/{norm}":
            probe_hits.append(path)
    corroborated = bool(found or probe_hits)
    return {
        "changed_paths": paths,
        "catalog_unit_ids_on_paths": sorted(found),
        "probe_tree_paths": probe_hits,
        "path_corroborated_program_work": corroborated,
        "class": "UNIT-CORROBORATED" if corroborated else "NO-UNIT-SURFACE",
    }


def commit_paths(repo: Path, sha: str) -> list[str]:
    proc = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha)
    return [line for line in (proc.stdout or "").splitlines() if line]


def log_since(repo: Path, baseline: str) -> list[dict[str, Any]]:
    fmt = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%ad%x1f%s"
    proc = git(
        repo,
        "log",
        "--format=" + fmt,
        "--date=iso-strict",
        f"{baseline}..HEAD",
    )
    if proc.returncode != 0:
        return []
    rows: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split("\x1f")
        if len(parts) < 7:
            continue
        rows.append(
            {
                "sha": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "committer_name": parts[3],
                "committer_email": parts[4],
                "author_date": parts[5],
                "subject": parts[6],
                "identity_forgeable": True,
            }
        )
    return rows


def _commit(repo: Path, message: str, *, name: str, email: str) -> str:
    extra = {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
    }
    proc = git(repo, "commit", "-q", "-m", message, extra_env=extra)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "commit failed")[:800])
    sha = git(repo, "rev-parse", "HEAD")
    return (sha.stdout or "").strip()


def build_ancestor_fixture() -> dict[str, Any]:
    """Owner scratch stays GREEN under is-ancestor; rewrite goes RED.

    Equality-to-pinned-SHA would go RED on the owner scratch; that is why
    the invariant must not be expressed as equality.
    """
    with tempfile.TemporaryDirectory(prefix="aud0008-anc-") as td:
        repo = Path(td)
        git(repo, "init", "-q")
        (repo / "README").write_text("baseline\n", encoding="utf-8")
        git(repo, "add", "README")
        baseline = _commit(
            repo,
            "baseline pin analog of 53c37c6c",
            name="Owner",
            email="owner@invalid.test",
        )
        (repo / "owner-scratch.txt").write_text("owner work\n", encoding="utf-8")
        git(repo, "add", "owner-scratch.txt")
        scratch = _commit(
            repo,
            "owner scratch on top of baseline",
            name="Owner",
            email="owner@invalid.test",
        )
        after_scratch = merge_base_is_ancestor(repo, baseline, scratch)
        strawman_scratch = equality_strawman(repo, baseline, scratch)
        tree = git(repo, "write-tree")
        rewritten = git(
            repo,
            "commit-tree",
            (tree.stdout or "").strip(),
            "-m",
            "history-rewrite root with no parent",
            extra_env={
                "GIT_AUTHOR_NAME": "Rewriter",
                "GIT_AUTHOR_EMAIL": "rewrite@invalid.test",
                "GIT_COMMITTER_NAME": "Rewriter",
                "GIT_COMMITTER_EMAIL": "rewrite@invalid.test",
            },
        )
        rewrite_sha = (rewritten.stdout or "").strip()
        after_rewrite = merge_base_is_ancestor(repo, baseline, rewrite_sha)
        return {
            "baseline_sha": baseline,
            "owner_scratch_sha": scratch,
            "rewritten_root_sha": rewrite_sha,
            "owner_scratch_is_ancestor": after_scratch["is_ancestor"],
            "owner_scratch_head_equals_baseline": strawman_scratch,
            "rewrite_is_ancestor": after_rewrite["is_ancestor"],
            "invariant_green_on_owner_scratch": after_scratch["is_ancestor"]
            and not strawman_scratch,
            "invariant_red_on_rewrite": not after_rewrite["is_ancestor"],
            "equality_strawman_would_fail_owner_scratch": strawman_scratch is False
            and after_scratch["is_ancestor"] is True,
            "pass": (
                after_scratch["is_ancestor"] is True
                and strawman_scratch is False
                and after_rewrite["is_ancestor"] is False
            ),
            "owner_scratch_is_ancestor": after_scratch["is_ancestor"],
            "rewrite_is_ancestor": after_rewrite["is_ancestor"],
            "owner_scratch_head_equals_baseline": strawman_scratch,
            "invariant_green_on_owner_scratch": after_scratch["is_ancestor"]
            and not strawman_scratch,
            "invariant_red_on_rewrite": not after_rewrite["is_ancestor"],
            "equality_strawman_would_fail_owner_scratch": strawman_scratch is False
            and after_scratch["is_ancestor"] is True,
        }


def build_path_fixture(unit_ids: set[str]) -> dict[str, Any]:
    """Identity is forgeable; path surface is the corroborating instrument.

    Commit A: Claude author, README only -> NO-UNIT-SURFACE
    Commit B: owner author, AUD-0008 probe path -> UNIT-CORROBORATED
    """
    with tempfile.TemporaryDirectory(prefix="aud0008-path-") as td:
        repo = Path(td)
        git(repo, "init", "-q")
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        git(repo, "add", "README.md")
        forged_agent = _commit(
            repo,
            "forged Claude identity on a non-unit path",
            name="Claude",
            email="noreply@anthropic.com",
        )
        plant = repo / "command-center" / "p2-wave" / "probes" / "AUD-0008" / "note.txt"
        plant.parent.mkdir(parents=True, exist_ok=True)
        plant.write_text("unit work\n", encoding="utf-8")
        git(repo, "add", "command-center/p2-wave/probes/AUD-0008/note.txt")
        forged_owner = _commit(
            repo,
            "forged owner identity on AUD-0008 probe path",
            name="Prekzursil",
            email="prekzursil@owner.test",
        )
        a_paths = commit_paths(repo, forged_agent)
        b_paths = commit_paths(repo, forged_owner)
        a = classify_paths(a_paths, unit_ids)
        b = classify_paths(b_paths, unit_ids)
        distinguished = (
            a["class"] == "NO-UNIT-SURFACE" and b["class"] == "UNIT-CORROBORATED"
        )
        return {
            "forged_agent_identity_commit": {
                "sha": forged_agent,
                "author_name": "Claude",
                "paths": a_paths,
                "path_class": a["class"],
                "catalog_unit_ids_on_paths": a["catalog_unit_ids_on_paths"],
            },
            "forged_owner_identity_commit": {
                "sha": forged_owner,
                "author_name": "Prekzursil",
                "paths": b_paths,
                "path_class": b["class"],
                "catalog_unit_ids_on_paths": b["catalog_unit_ids_on_paths"],
            },
            "identity_ignored_for_verdict": True,
            "path_surface_distinguishes": distinguished,
            "pass": distinguished,
        }


def discover_live_repos(root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(worktree: Path) -> None:
        worktree = worktree.resolve()
        if str(worktree) in seen:
            return
        if not is_git_repo(worktree):
            return
        top = git(worktree, "rev-parse", "--show-toplevel")
        toplevel = Path((top.stdout or str(worktree)).strip()).resolve()
        if str(toplevel) in seen:
            return
        seen.add(str(toplevel))
        root_res = root.resolve()
        if root_res in toplevel.parents or toplevel == root_res:
            rel = toplevel.relative_to(root_res).as_posix() or "."
        else:
            rel = str(toplevel)
        found.append({"path": str(toplevel), "rel": rel})

    add(root)
    for dirpath, dirnames, _filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if (Path(dirpath) / ".git").exists():
            add(Path(dirpath))
        if len(found) >= 32:
            break
    return found


def census_live(unit_ids: set[str]) -> dict[str, Any]:
    root = REPO
    inside = is_git_repo(root)
    marker = (root / ".git").exists()
    repos = discover_live_repos(root) if inside or marker else []
    rows: list[dict[str, Any]] = []
    for rec in repos:
        repo = Path(rec["path"])
        anc = merge_base_is_ancestor(repo, PINNED_BASELINE, "HEAD")
        intervening: list[dict[str, Any]] = []
        if anc["is_ancestor"] and not anc["baseline_object_missing"]:
            for commit in log_since(repo, PINNED_BASELINE):
                paths = commit_paths(repo, commit["sha"])
                classified = classify_paths(paths, unit_ids)
                intervening.append({**commit, **classified})
        rows.append(
            {
                "repo": rec["rel"],
                "abs_path": rec["path"],
                "ancestor": anc,
                "intervening_commit_count": len(intervening),
                "intervening_commits": intervening[:200],
                "unit_corroborated_commit_count": sum(
                    1 for c in intervening if c.get("class") == "UNIT-CORROBORATED"
                ),
                "no_unit_surface_commit_count": sum(
                    1 for c in intervening if c.get("class") == "NO-UNIT-SURFACE"
                ),
                "unit_corroborated_commit_count": sum(
                    1 for c in intervening if c.get("class") == "UNIT-CORROBORATED"
                ),
            }
        )
    return {
        "worktree": str(root),
        "worktree_is_git": inside,
        "worktree_is_git": inside,
        "pinned_baseline": PINNED_BASELINE,
        "repos_in_scope": len(rows),
        "repos_in_scope": len(rows),
        "repos": rows,
        "other_owner_repos": "NOT-CHECKED",
        "other_owner_repos_why": (
            "Catalog asks per repo. This lane may scan this worktree only; "
            "walking ~ or sibling session trees is forbidden."
        ),
    }


def run_all() -> dict[str, Any]:
    unit_ids = load_unit_ids()
    ancestor_ctl = build_ancestor_fixture()
    path_ctl = build_path_fixture(unit_ids)
    live = census_live(unit_ids)
    live_all_ancestors = bool(live["repos"]) and all(
        r["ancestor"]["is_ancestor"] for r in live["repos"]
    )
    return {
        "pinned_baseline": PINNED_BASELINE,
        "catalog_unit_id_count": len(unit_ids),
        "catalog_unit_id_count": len(unit_ids),
        "probe1_control": ancestor_ctl,
        "probe2_control": path_ctl,
        "probe1_control": ancestor_ctl,
        "probe2_control": path_ctl,
        "live": live,
        "live_every_head_has_baseline_ancestor": live_all_ancestors,
        "live_every_head_has_baseline_ancestor": live_all_ancestors,
        "live_heads_present": bool(live["repos"]),
        "controls_pass": bool(ancestor_ctl["pass"] and path_ctl["pass"]),
        "controls_pass": bool(ancestor_ctl["pass"] and path_ctl["pass"]),
        "probe1_control": ancestor_ctl,
        "probe2_control": path_ctl,
        "catalog_unit_id_count": len(unit_ids),
        "catalog_unit_id_count": len(unit_ids),
    }


build_ancestor_fixture = build_ancestor_fixture
build_path_fixture = build_path_fixture
census_live = census_live
load_unit_ids = load_unit_ids
run_all = run_all
PINNED_BASELINE = PINNED_BASELINE
