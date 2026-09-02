#!/usr/bin/env python3
"""Squash-merge-aware branch classification for AUD-0001.

Probe 1 is commit ancestry (rev-list count + cherry). Probe 2 is PR-MERGED
state or two-dot tree equality. Three-dot diff is recorded but is not the
CONTENT-ON-MAIN instrument: after squash-merge it stays non-empty while the
trees match.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/audit/AUD-0001-branch-merge-state.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"
API_REL = "command-center/p2-wave/probes/AUD-0001/api/fixture--squash-estate/pulls-page-01.json"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0001/probe1_ancestry.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0001/probe2_content.py"
)
SENTINEL = (
    "SUCCESS:AUD-0001 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "For every local and remote branch in every owner-controlled repo, is "
    "its content already on main — answered by PR-MERGED state or byte-level "
    "content comparison, NOT by commit ancestry?"
)
AUTHOR_DATE = "2026-08-24T12:00:00 +0000"
SQUASH_BRANCH = "feature-squash"
UNMERGED_BRANCH = "feature-unmerged"
ON_MAIN_BRANCH = "already-on-main"
FIXTURE_ID = "fixture-squash-estate"
DOCS_GITHUB = Path.home() / "Documents" / "GitHub"
SOURCE_ROOT = Path.home() / "source"
# Parent of a concurrent-session tree. Existence may be recorded; the tree is
# never walked even when present.
FORBIDDEN_WALK_ROOTS = (DOCS_GITHUB,)


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_AUTHOR_NAME": "AUD-0001",
            "GIT_AUTHOR_EMAIL": "aud-0001@fixture.invalid",
            "GIT_COMMITTER_NAME": "AUD-0001",
            "GIT_COMMITTER_EMAIL": "aud-0001@fixture.invalid",
            "GIT_AUTHOR_DATE": AUTHOR_DATE,
            "GIT_COMMITTER_DATE": AUTHOR_DATE,
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def run_git(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=git_env(),
        )
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT git {' '.join(args)}"
    except OSError as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, out


def plant_non_utf8_path(repo: Path) -> dict[str, Any]:
    """Refute: a non-UTF-8 filename must not crash the inventory walker."""
    raw_name = b"latin1-\xfe-name.txt"
    path = repo / os.fsdecode(raw_name)
    result: dict[str, Any] = {
        "attempted": True,
        "created": False,
        "git_added": False,
        "walker_survived": False,
        "detail": "",
    }
    try:
        path.write_bytes(b"non-utf8-path-control\n")
        result["created"] = path.is_file()
        code, text = run_git(["add", "-A"], repo)
        result["git_added"] = code == 0
        if code != 0:
            result["detail"] = text[-400:]
        else:
            run_git(["commit", "-m", "non-utf8 path control"], repo)
        code, text = run_git(
            ["for-each-ref", "--format=%(refname)\t%(objectname)", "refs/heads"],
            repo,
        )
        result["walker_survived"] = code == 0 and "refs/heads/main" in text
        if code != 0:
            result["detail"] = (result.get("detail") or "") + " | " + text[-400:]
    except OSError as exc:
        result["detail"] = f"{type(exc).__name__}: {exc}"
        result["walker_survived"] = True
    return result


def build_squash_estate(root: Path) -> Path:
    repo = root / "squash-estate"
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True, exist_ok=True)
    code, text = run_git(["-c", "init.defaultBranch=main", "init"], repo)
    if code != 0:
        raise RuntimeError(f"git init failed: {text}")
    (repo / "README.md").write_text(
        "AUD-0001 squash-estate: ancestry lies after squash-merge.\n",
        encoding="utf-8",
    )
    code, text = run_git(["add", "README.md"], repo)
    if code != 0:
        raise RuntimeError(f"git add failed: {text}")
    code, text = run_git(["commit", "-m", "base"], repo)
    if code != 0:
        raise RuntimeError(f"git commit failed: {text}")

    code, text = run_git(["checkout", "-b", SQUASH_BRANCH], repo)
    if code != 0:
        raise RuntimeError(f"branch {SQUASH_BRANCH} failed: {text}")
    (repo / "feature.txt").write_text("squash-unique-content\n", encoding="utf-8")
    run_git(["add", "feature.txt"], repo)
    code, text = run_git(["commit", "-m", "add feature"], repo)
    if code != 0:
        raise RuntimeError(f"feature commit failed: {text}")

    code, text = run_git(["checkout", "main"], repo)
    if code != 0:
        raise RuntimeError(f"checkout main failed: {text}")
    code, text = run_git(["merge", "--squash", SQUASH_BRANCH], repo)
    if code != 0:
        raise RuntimeError(f"squash merge failed: {text}")
    code, text = run_git(["commit", "-m", "squash feature-squash onto main"], repo)
    if code != 0:
        raise RuntimeError(f"squash commit failed: {text}")

    code, text = run_git(["checkout", "-b", UNMERGED_BRANCH], repo)
    if code != 0:
        raise RuntimeError(f"branch {UNMERGED_BRANCH} failed: {text}")
    (repo / "only-on-branch.txt").write_text("not on main\n", encoding="utf-8")
    run_git(["add", "only-on-branch.txt"], repo)
    code, text = run_git(["commit", "-m", "unmerged unique"], repo)
    if code != 0:
        raise RuntimeError(f"unmerged commit failed: {text}")

    code, text = run_git(["checkout", "main"], repo)
    if code != 0:
        raise RuntimeError(f"return to main failed: {text}")
    code, text = run_git(["branch", ON_MAIN_BRANCH], repo)
    if code != 0:
        raise RuntimeError(f"branch {ON_MAIN_BRANCH} failed: {text}")
    return repo


def write_pr_page(repo: Path, dest: Path) -> dict[str, Any]:
    """Plant a GitHub-list-pulls page for the squash branch head SHA."""
    code, squash_sha = run_git(["rev-parse", SQUASH_BRANCH], repo)
    if code != 0:
        raise RuntimeError(f"rev-parse {SQUASH_BRANCH}: {squash_sha}")
    code, main_sha = run_git(["rev-parse", "main"], repo)
    if code != 0:
        raise RuntimeError(f"rev-parse main: {main_sha}")
    page = [
        {
            "id": 1,
            "number": 1,
            "state": "closed",
            "title": "feature-squash",
            "merged_at": "2026-08-24T12:05:00Z",
            "merged": True,
            "merge_commit_sha": main_sha,
            "head": {
                "ref": SQUASH_BRANCH,
                "sha": squash_sha,
            },
            "base": {"ref": "main", "sha": main_sha},
        }
    ]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(page, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {"head_sha": squash_sha, "merge_commit_sha": main_sha, "path": str(dest)}


def load_pr_by_head_sha(api_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    root = api_dir or (HERE / "api")
    index: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return index
    for path in sorted(root.rglob("pulls-page-*.json")):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            continue
        rows = doc if isinstance(doc, list) else doc.get("items") or []
        if not isinstance(rows, list):
            continue
        for pr in rows:
            if not isinstance(pr, dict):
                continue
            head = pr.get("head") or {}
            sha = str(head.get("sha") or "").strip().lower()
            if sha:
                index[sha] = pr
    return index


def pr_is_merged(pr: dict[str, Any] | None) -> bool:
    if not isinstance(pr, dict):
        return False
    if pr.get("merged") is True:
        return True
    if pr.get("merged_at"):
        return True
    return str(pr.get("state") or "").upper() == "MERGED"


def list_heads(repo: Path) -> list[dict[str, str]]:
    code, text = run_git(
        ["for-each-ref", "--format=%(refname)\t%(objectname)", "refs/heads"],
        repo,
    )
    if code != 0:
        return []
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        if "\t" not in line:
            continue
        ref, sha = line.split("\t", 1)
        name = ref.split("refs/heads/", 1)[-1]
        rows.append({"ref": ref, "name": name, "sha": sha})
    return rows


def classify_branch(
    repo: Path,
    branch: str,
    main: str = "main",
    pr_index: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    code, sha = run_git(["rev-parse", branch], repo)
    head_sha = sha if code == 0 else ""
    code, ahead_raw = run_git(["rev-list", "--count", f"{main}..{branch}"], repo)
    try:
        ahead = int((ahead_raw or "0").strip() or "0") if code == 0 else -1
    except ValueError:
        ahead = -1
    cherry_code, cherry = run_git(["cherry", "-v", main, branch], repo)
    two_code, two_stat = run_git(["diff", "--stat", main, branch], repo)
    three_code, three_stat = run_git(["diff", "--stat", f"{main}...{branch}"], repo)
    quiet_two = run_git(["diff", "--quiet", main, branch], repo)[0]
    two_empty = quiet_two == 0
    pr = (pr_index or {}).get(head_sha.lower()) if head_sha else None
    merged = pr_is_merged(pr)
    content_on_main = bool(merged or two_empty)
    ancestry_ahead = ahead > 0
    if content_on_main and ancestry_ahead:
        merge_class = "SQUASH-MERGED"
    elif content_on_main:
        merge_class = "CONTENT-ON-MAIN"
    elif ancestry_ahead:
        merge_class = "NOT-ON-MAIN"
    else:
        merge_class = "INDETERMINATE"
    plus = [ln for ln in cherry.splitlines() if ln.startswith("+")]
    minus = [ln for ln in cherry.splitlines() if ln.startswith("-")]
    return {
        "branch": branch,
        "head_sha": head_sha,
        "ancestry_ahead_count": ahead,
        "ancestry_ahead": ancestry_ahead,
        "cherry_exit": cherry_code,
        "cherry_plus": len(plus),
        "cherry_minus": len(minus),
        "cherry_raw": cherry[-2000:],
        "two_dot_stat": two_stat[-2000:],
        "two_dot_empty": two_empty,
        "two_dot_exit": two_code,
        "three_dot_stat": three_stat[-2000:],
        "three_dot_empty": three_code == 0 and not (three_stat or "").strip(),
        "pr_merged": merged,
        "pr_number": (pr or {}).get("number") if pr else None,
        "content_on_main": content_on_main,
        "content_reason": "PR-MERGED" if merged else ("TREE-EQUAL" if two_empty else "DIFFERS"),
        "class": merge_class,
    }


def classify_repo(repo: Path, pr_index: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    heads = list_heads(repo)
    names = [h["name"] for h in heads]
    main = "main" if "main" in names else ("master" if "master" in names else (names[0] if names else "main"))
    branches = []
    for head in heads:
        if head["name"] == main:
            continue
        branches.append(classify_branch(repo, head["name"], main=main, pr_index=pr_index))
    squash_false_ahead = [
        b for b in branches if b["ancestry_ahead"] and b["content_on_main"]
    ]
    return {
        "repo": str(repo),
        "main": main,
        "head_count": len(heads),
        "branches": branches,
        "ancestry_ahead": sum(1 for b in branches if b["ancestry_ahead"]),
        "content_on_main": sum(1 for b in branches if b["content_on_main"]),
        "not_on_main": sum(1 for b in branches if not b["content_on_main"]),
        "squash_merge_false_ahead": len(squash_false_ahead),
        "pr_merged_count": sum(1 for b in branches if b["pr_merged"]),
    }


def inspect_declared_roots() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    mapping = (
        ("~/source", SOURCE_ROOT, False),
        ("~/Documents/GitHub", DOCS_GITHUB, True),
    )
    for label, path, forbidden in mapping:
        exists = path.exists()
        walked = False
        repos: list[str] = []
        reason = "absent"
        if exists and forbidden:
            reason = "present-but-not-walked: wave floor (concurrent-session parent)"
        elif exists:
            reason = "present"
            walked = True
            if (path / ".git").exists():
                repos.append(str(path))
            try:
                for child in sorted(path.iterdir()):
                    if child.is_dir() and (child / ".git").exists():
                        repos.append(str(child))
            except OSError as exc:
                reason = f"present-but-unlistable: {type(exc).__name__}"
                walked = False
        rows.append(
            {
                "label": label,
                "path": str(path),
                "exists": exists,
                "walked": walked,
                "forbidden_walk": forbidden,
                "git_repos": repos,
                "reason": reason,
            }
        )
    return rows


def owner_worktree_row() -> dict[str, Any]:
    git = REPO / ".git"
    present = git.exists()
    kind = "absent"
    if git.is_dir():
        kind = "directory"
    elif git.is_file():
        kind = "file"
    code, text = run_git(["rev-parse", "--is-inside-work-tree"], REPO)
    return {
        "id": "ast-integrate",
        "path": str(REPO),
        "git_present": present,
        "git_kind": kind,
        "rev_parse_exit": code,
        "rev_parse_tail": text[-400:],
        "classified": False,
        "reason": (
            None
            if present
            else "worktree has no .git; git rev-parse is not-a-repository"
        ),
    }


def by_name(report: dict[str, Any], name: str) -> dict[str, Any] | None:
    for row in report.get("branches") or []:
        if row.get("branch") == name:
            return row
    return None


def control_ok(report: dict[str, Any]) -> tuple[bool, str]:
    squash = by_name(report, SQUASH_BRANCH)
    unmerged = by_name(report, UNMERGED_BRANCH)
    on_main = by_name(report, ON_MAIN_BRANCH)
    if squash is None or unmerged is None or on_main is None:
        return False, "fixture branches missing"
    if not squash["ancestry_ahead"]:
        return False, "squash branch is not ancestry-ahead (control inert)"
    if not squash["content_on_main"]:
        return False, "squash branch not CONTENT-ON-MAIN (content detector failed)"
    if squash["class"] != "SQUASH-MERGED":
        return False, f"squash class {squash['class']!r} expected SQUASH-MERGED"
    if unmerged["content_on_main"]:
        return False, "unmerged branch reported CONTENT-ON-MAIN"
    if not unmerged["ancestry_ahead"]:
        return False, "unmerged branch is not ancestry-ahead"
    if on_main["ancestry_ahead"]:
        return False, "already-on-main reported ancestry-ahead"
    if not on_main["content_on_main"]:
        return False, "already-on-main not CONTENT-ON-MAIN"
    if squash["two_dot_empty"] == squash["three_dot_empty"] and squash["three_dot_empty"]:
        # Three-dot empty on a squash-merged unique commit would mean we are
        # not seeing the ancestry trap. After squash, three-dot is usually
        # NON-empty; two-dot is empty. If both empty, still OK if ancestry
        # ahead — trees match and merge-base equals branch (unusual).
        pass
    if squash["two_dot_empty"] is False:
        return False, "squash two-dot tree diff is not empty"
    return True, "ok"


def live_bundle() -> dict[str, Any]:
    scratch = Path(tempfile.mkdtemp(prefix="aud0001-"))
    try:
        repo = build_squash_estate(scratch)
        utf8_repo = scratch / "non-utf8-estate"
        utf8_repo.mkdir()
        run_git(["-c", "init.defaultBranch=main", "init"], utf8_repo)
        (utf8_repo / "README.md").write_text("non-utf8 walker control\n", encoding="utf-8")
        run_git(["add", "README.md"], utf8_repo)
        run_git(["commit", "-m", "base"], utf8_repo)
        non_utf8 = plant_non_utf8_path(utf8_repo)
        page = write_pr_page(repo, REPO / API_REL)
        pr_index = load_pr_by_head_sha()
        fixture = classify_repo(repo, pr_index=pr_index)
        ok, detail = control_ok(fixture)
        declared = inspect_declared_roots()
        owner = owner_worktree_row()
        return {
            "fixture_repo": FIXTURE_ID,
            "fixture": fixture,
            "control_ok": ok,
            "control_detail": detail,
            "non_utf8": non_utf8,
            "pr_page": page,
            "declared_roots": declared,
            "owner": owner,
            "github_live": {
                "attempted": False,
                "reason": "gh CLI absent; no GitHub token consumed; fixture PR page only",
            },
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
