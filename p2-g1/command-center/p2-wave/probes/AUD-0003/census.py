#!/usr/bin/env python3
"""AUD-0003 PR unique-content detector.

Probe 1 instrument (catalog): git diff <head> main --name-only, then keep only
paths the PR actually touched.

Probe 2 instrument (catalog): GitHub merged_at plus merge_commit_sha
reachability from main. Absence is called deliberate only when those two
signals agree that the PR merged.

Negative control (catalog): a fully-merged PR reports zero missing files;
deleting one of its files in a local copy of main makes the detector report
exactly one. The live ast-integrate worktree is never mutated.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

UNIT = "AUD-0003"
MAIN = "main"
FIXTURE_OWNER = "aud-0003-fixture"
FIXTURE_REPO = "census"

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "AUD-0003",
    "GIT_AUTHOR_EMAIL": "aud-0003@fixture.invalid",
    "GIT_COMMITTER_NAME": "AUD-0003",
    "GIT_COMMITTER_EMAIL": "aud-0003@fixture.invalid",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_OPTIONAL_LOCKS": "0",
    "GC_AUTO": "0",
}


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return parent
    raise RuntimeError("AUD-0003: cannot locate worktree root")


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = [
        "git",
        "-C",
        str(repo),
        "-c",
        "user.name=AUD-0003",
        "-c",
        "user.email=aud-0003@fixture.invalid",
        "-c",
        "commit.gpgsign=false",
        "-c",
        "init.defaultBranch=main",
        *args,
    ]
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=GIT_ENV,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} rc={proc.returncode} stderr={(proc.stderr or '')[:800]}"
        )
    return proc


def write_text(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="\n")


def sha(repo: Path, ref: str = "HEAD") -> str:
    return git(repo, "rev-parse", ref).stdout.strip()


def name_only(repo: Path, *diff_args: str) -> list[str]:
    text = git(repo, "diff", "--name-only", *diff_args).stdout
    return [line.strip().replace("\\", "/") for line in text.splitlines() if line.strip()]


def touched_files(repo: Path, head: str, base: str) -> list[str]:
    """Files the PR changed relative to the merge-base *at open*, not current main.

    After a PR is merged, `git diff main...head` is empty because head is an
    ancestor of main. The GitHub files list is the diff against the base SHA
    recorded when the PR existed, so Probe 1 can still limit to those paths.
    """
    return name_only(repo, f"{base}...{head}")


def diff_head_main(repo: Path, head: str, main: str = MAIN) -> list[str]:
    """Catalog Probe 1: git diff <head> main --name-only."""
    return name_only(repo, head, main)


def missing_vs_refs(repo: Path, head: str, touched: list[str], main: str = MAIN) -> list[str]:
    changed = set(diff_head_main(repo, head, main))
    return sorted(path for path in touched if path in changed)


def missing_vs_worktree(workdir: Path, head: str, touched: list[str]) -> list[str]:
    """Compare PR head to the current working tree (local-delete control)."""
    changed = set(name_only(workdir, head))
    return sorted(path for path in touched if path in changed)


def is_ancestor(repo: Path, commit: str | None, ref: str = MAIN) -> bool:
    if not commit:
        return False
    proc = git(repo, "merge-base", "--is-ancestor", commit, ref, check=False)
    return proc.returncode == 0


def revert_subjects_touching(repo: Path, merge_sha: str, missing: list[str]) -> list[str]:
    """Revert commits after merge_sha that actually touch the missing paths."""
    text = git(repo, "log", "--format=%H\t%s", f"{merge_sha}..{MAIN}").stdout
    hits: list[str] = []
    missing_set = set(missing)
    for line in text.splitlines():
        if "\t" not in line:
            continue
        commit_sha, subject = line.split("\t", 1)
        if not subject.lower().startswith("revert"):
            continue
        names = set(name_only_tree(repo, commit_sha.strip()))
        if names & missing_set:
            hits.append(subject.strip())
    return hits


def name_only_tree(repo: Path, commit_sha: str) -> list[str]:
    text = git(
        repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha
    ).stdout
    return [line.strip().replace("\\", "/") for line in text.splitlines() if line.strip()]


def blob_at(repo: Path, ref: str, path: str) -> str | None:
    proc = git(repo, "cat-file", "-e", f"{ref}:{path}", check=False)
    if proc.returncode != 0:
        return None
    return git(repo, "show", f"{ref}:{path}").stdout


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)
    return sha(repo)


def merge_no_ff(repo: Path, branch: str, message: str) -> str:
    git(repo, "checkout", MAIN)
    git(repo, "merge", "--no-ff", "--no-edit", "-m", message, branch)
    return sha(repo)


def github_record(
    number: int,
    title: str,
    head_sha: str,
    files: list[str],
    *,
    merged_at: str | None,
    merge_commit_sha: str | None,
    merge_base_sha: str,
    state: str = "closed",
) -> dict[str, Any]:
    return {
        "number": number,
        "title": title,
        "state": state,
        "merged_at": merged_at,
        "merge_commit_sha": merge_commit_sha,
        "head": {"sha": head_sha, "ref": f"pr-{number}"},
        "base": {"ref": MAIN, "sha": merge_base_sha},
        "html_url": f"https://github.com/{FIXTURE_OWNER}/{FIXTURE_REPO}/pull/{number}",
        "files": list(files),
        "source": "fixture-github-api",
    }


def build_fixture(root: Path) -> dict[str, Any]:
    """Plant merged, closed-without-merge, superseded, reverted, and force-push PRs."""
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    git(root, "init", "-b", MAIN)
    write_text(root / "README.txt", "fixture main seed\n")
    write_text(root / "keep.txt", "stable-bytes-never-removed\n")
    commit(root, "main: seed")

    def plant_branch(number: int, rel: str, body: str, message: str) -> tuple[str, str, list[str]]:
        git(root, "checkout", MAIN)
        base = sha(root, MAIN)
        git(root, "checkout", "-b", f"pr-{number}")
        write_text(root / rel, body)
        head = commit(root, message)
        files = touched_files(root, head, base)
        return base, head, files

    # PR 10 — fully merged; content remains on main.
    pr10_base, pr10_head, pr10_files = plant_branch(
        10, "features/landed.txt", "pr-10-landed-body\n", "PR-10 add features/landed.txt"
    )
    pr10_merge = merge_no_ff(root, "pr-10", "Merge pull request #10 from pr-10")

    # PR 11 — closed without merge; unique content never on main.
    pr11_base, pr11_head, pr11_files = plant_branch(
        11,
        "features/closed-only.txt",
        "pr-11-closed-without-merge-bytes\n",
        "PR-11 add features/closed-only.txt",
    )
    git(root, "checkout", MAIN)

    # PR 12 — merged widget v1, later superseded by PR 13.
    pr12_base, pr12_head, pr12_files = plant_branch(
        12, "features/widget.py", "WIDGET_VERSION = 1\n", "PR-12 add widget v1"
    )
    pr12_merge = merge_no_ff(root, "pr-12", "Merge pull request #12 from pr-12")

    # PR 13 — merged widget v2 (supersedes PR 12).
    pr13_base, pr13_head, pr13_files = plant_branch(
        13, "features/widget.py", "WIDGET_VERSION = 2\n", "PR-13 supersede widget v2"
    )
    pr13_merge = merge_no_ff(root, "pr-13", "Merge pull request #13 from pr-13")

    # PR 14 — merged then reverted on main.
    pr14_base, pr14_head, pr14_files = plant_branch(
        14, "features/doomed.txt", "pr-14-doomed-bytes\n", "PR-14 add features/doomed.txt"
    )
    pr14_merge = merge_no_ff(root, "pr-14", "Merge pull request #14 from pr-14")
    git(root, "revert", "-m", "1", "--no-edit", pr14_merge)
    pr14_revert = sha(root)

    # PR 15 — GitHub claims merged, but merge commit is not reachable from main.
    pr15_base, pr15_head, pr15_files = plant_branch(
        15,
        "features/force-push-only.txt",
        "pr-15-force-push-bytes\n",
        "PR-15 add features/force-push-only.txt",
    )
    git(root, "checkout", "-b", "pr-15-merge-target", MAIN)
    git(
        root,
        "merge",
        "--no-ff",
        "--no-edit",
        "-m",
        "Merge pull request #15 from pr-15",
        "pr-15",
    )
    pr15_merge = sha(root)
    git(root, "checkout", MAIN)

    github = [
        github_record(
            10,
            "fully merged landed feature",
            pr10_head,
            pr10_files,
            merged_at="2026-01-10T00:00:00Z",
            merge_commit_sha=pr10_merge,
            merge_base_sha=pr10_base,
        ),
        github_record(
            11,
            "closed without merge",
            pr11_head,
            pr11_files,
            merged_at=None,
            merge_commit_sha=None,
            merge_base_sha=pr11_base,
        ),
        github_record(
            12,
            "widget v1 later superseded",
            pr12_head,
            pr12_files,
            merged_at="2026-02-10T00:00:00Z",
            merge_commit_sha=pr12_merge,
            merge_base_sha=pr12_base,
        ),
        github_record(
            13,
            "widget v2 supersedes v1",
            pr13_head,
            pr13_files,
            merged_at="2026-03-10T00:00:00Z",
            merge_commit_sha=pr13_merge,
            merge_base_sha=pr13_base,
        ),
        github_record(
            14,
            "merged then reverted",
            pr14_head,
            pr14_files,
            merged_at="2026-04-10T00:00:00Z",
            merge_commit_sha=pr14_merge,
            merge_base_sha=pr14_base,
        ),
        github_record(
            15,
            "GitHub merged_at but merge commit unreachable (force-push)",
            pr15_head,
            pr15_files,
            merged_at="2026-05-10T00:00:00Z",
            merge_commit_sha=pr15_merge,
            merge_base_sha=pr15_base,
        ),
    ]
    return {
        "repo": str(root),
        "main_sha": sha(root, MAIN),
        "github": github,
        "pr14_revert_sha": pr14_revert,
        "fully_merged_pr": 10,
        "fully_merged_file": "features/landed.txt",
    }


def classify_loss(
    repo: Path,
    record: dict[str, Any],
    missing: list[str],
    all_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Absence is deliberate only when GitHub merged_at and reachability agree."""
    merged_at = record.get("merged_at")
    merge_sha = record.get("merge_commit_sha")
    github_merged = bool(merged_at)
    reachable = is_ancestor(repo, merge_sha, MAIN)
    agree = github_merged == reachable
    result: dict[str, Any] = {
        "number": record["number"],
        "github_merged_at": merged_at,
        "merge_commit_sha": merge_sha,
        "github_merged": github_merged,
        "merge_commit_reachable_from_main": reachable,
        "mergedness_agrees": agree,
        "missing_files": missing,
        "loss": None,
        "deliberate": False,
        "reason": "no unique content absent from main",
    }
    if not missing:
        return result
    if not agree:
        result["loss"] = "accidental-force-push-or-unreachable-merge"
        result["reason"] = (
            "GitHub merged_at and merge_commit_sha reachability disagree; "
            "absence is not called deliberate"
        )
        return result
    if not github_merged:
        result["loss"] = "accidental-closed-without-merge"
        result["reason"] = "closed without merge; both signals agree not-merged"
        return result
    # Both agree the PR merged, yet content is absent from main today.
    later = [
        other
        for other in all_records
        if other["number"] != record["number"]
        and other.get("merged_at")
        and other.get("merged_at", "") > (merged_at or "")
        and is_ancestor(repo, other.get("merge_commit_sha"), MAIN)
        and set(other.get("files") or []) & set(missing)
    ]
    still_on_main = []
    for path in missing:
        head_blob = blob_at(repo, record["head"]["sha"], path)
        main_blob = blob_at(repo, MAIN, path)
        if head_blob is not None and main_blob == head_blob:
            still_on_main.append(path)
    if still_on_main:
        result["loss"] = "detector-inconsistent"
        result["reason"] = f"missing list still matches main blobs: {still_on_main}"
        return result
    if later:
        result["loss"] = "deliberate-superseded"
        result["deliberate"] = True
        result["superseded_by"] = [row["number"] for row in later]
        result["reason"] = (
            "both signals agree merged; a later merged PR replaced the same path(s)"
        )
        return result
    revert_hits = revert_subjects_touching(repo, merge_sha, missing) if merge_sha else []
    if revert_hits:
        result["loss"] = "accidental-revert"
        result["reason"] = f"post-merge revert commit(s) touching missing paths: {revert_hits[:3]}"
        return result
    result["loss"] = "accidental-unknown-post-merge-loss"
    result["reason"] = (
        "both signals agree merged, content absent, no path-touching revert and no later PR"
    )
    return result


def census_fixture(world: dict[str, Any]) -> dict[str, Any]:
    repo = Path(world["repo"])
    rows = []
    for record in world["github"]:
        head = record["head"]["sha"]
        touched = list(record["files"])
        base = str((record.get("base") or {}).get("sha") or "")
        recomputed = touched_files(repo, head, base) if base else []
        if set(recomputed) != set(touched):
            raise RuntimeError(
                f"PR {record['number']} files drift fixture={touched} git={recomputed}"
            )
        unlimited = diff_head_main(repo, head)
        missing = missing_vs_refs(repo, head, touched)
        command = f"git diff --name-only {head} {MAIN}"
        classified = classify_loss(repo, record, missing, world["github"])
        rows.append(
            {
                **classified,
                "title": record["title"],
                "head_sha": head,
                "touched_files": touched,
                "unlimited_diff_name_only": unlimited,
                "unlimited_diff_count": len(unlimited),
                "probe1_command": command,
                "probe1_limited_missing": missing,
            }
        )
    unique = [row for row in rows if row["missing_files"]]
    return {
        "fixture_repo": world["repo"],
        "main_sha": world["main_sha"],
        "pr_count": len(rows),
        "prs_with_content_absent_from_main": unique,
        "absent_count": len(unique),
        "rows": rows,
    }


def both_states_control(world: dict[str, Any]) -> dict[str, Any]:
    repo = Path(world["repo"])
    pr_no = int(world["fully_merged_pr"])
    record = next(r for r in world["github"] if r["number"] == pr_no)
    head = record["head"]["sha"]
    touched = list(record["files"])
    target = str(world["fully_merged_file"])
    good_missing = missing_vs_worktree(repo, head, touched)
    ctl = Path(tempfile.mkdtemp(prefix="aud0003-ctl-"))
    try:
        shutil.copytree(repo, ctl, dirs_exist_ok=True)
        doomed = ctl / target
        if not doomed.is_file():
            raise RuntimeError(f"control target absent in copy: {target}")
        doomed.unlink()
        bad_missing = missing_vs_worktree(ctl, head, touched)
    finally:
        shutil.rmtree(ctl, ignore_errors=True)
    silent = good_missing == []
    fires = bad_missing == [target]
    return {
        "id": "AUD-0003-C1-fully-merged-then-local-delete",
        "kind": "known-broken-fixture",
        "description": (
            "Pick a PR known to be fully merged and confirm the detector reports "
            "zero missing files; then delete one of its files locally (temp copy, "
            "not the ast-integrate worktree) and confirm it reports exactly one."
        ),
        "pr": pr_no,
        "file": target,
        "good_state_missing": good_missing,
        "bad_state_missing": bad_missing,
        "silent_on_good_state": silent,
        "fired_on_bad_state": fires,
        "pass": silent and fires,
    }


def live_owner_attempt(root: Path) -> dict[str, Any]:
    """Honest attempt at the catalog's live GitHub PR list. Never prints secrets."""
    git_dir = root / ".git"
    token_names = [
        name
        for name in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")
        if os.environ.get(name)
    ]
    gh_path = shutil.which("gh")
    api: dict[str, Any]
    try:
        req = urllib.request.Request(
            "https://api.github.com/rate_limit",
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "AUD-0003-pr-census",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            core = (payload.get("resources") or {}).get("core") or {}
            api = {
                "ok": True,
                "http_status": int(resp.status),
                "limit": core.get("limit"),
                "authenticated_limit_is_unauth_floor": core.get("limit") in {60, None},
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as exc:
        api = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)[:240]}
    reasons = []
    if not git_dir.exists():
        reasons.append("worktree-has-no-git-metadata")
    if gh_path is None:
        reasons.append("gh-cli-absent")
    if not token_names:
        reasons.append("github-token-env-absent")
    return {
        "worktree_is_git": git_dir.is_dir(),
        "gh_cli_present": gh_path is not None,
        "github_token_env_present": bool(token_names),
        "github_token_env_names": token_names,
        "owner_repo_configured": False,
        "live_prs": [],
        "live_pr_count": 0,
        "not_checked_reason": reasons,
        "github_api_unauthenticated_probe": api,
        "note": (
            "Live owner-repo PR census is NOT-CHECKED. Treating that gap as "
            "zero missing PRs would be a false green."
        ),
    }


def expected_rows_ok(census: dict[str, Any]) -> list[str]:
    by_no = {row["number"]: row for row in census["rows"]}
    errors: list[str] = []

    r10 = by_no[10]
    if r10["missing_files"]:
        errors.append(f"PR10 fully-merged should have 0 missing, got {r10['missing_files']}")
    if r10["unlimited_diff_count"] == 0:
        errors.append("PR10 unlimited git diff vs main was empty; limit-to-touched is untested")

    r11 = by_no[11]
    if r11["missing_files"] != ["features/closed-only.txt"]:
        errors.append(f"PR11 missing want [features/closed-only.txt] got {r11['missing_files']}")
    if r11["loss"] != "accidental-closed-without-merge":
        errors.append(f"PR11 loss={r11['loss']}")
    if r11["deliberate"]:
        errors.append("PR11 must not be called deliberate")

    r12 = by_no[12]
    if r12["missing_files"] != ["features/widget.py"]:
        errors.append(f"PR12 missing want [features/widget.py] got {r12['missing_files']}")
    if r12["loss"] != "deliberate-superseded" or not r12["deliberate"]:
        errors.append(f"PR12 want deliberate-superseded got {r12['loss']} deliberate={r12['deliberate']}")

    r13 = by_no[13]
    if r13["missing_files"]:
        errors.append(f"PR13 current widget v2 should have 0 missing, got {r13['missing_files']}")

    r14 = by_no[14]
    if r14["missing_files"] != ["features/doomed.txt"]:
        errors.append(f"PR14 missing want [features/doomed.txt] got {r14['missing_files']}")
    if r14["loss"] != "accidental-revert":
        errors.append(f"PR14 loss={r14['loss']}")
    if r14["deliberate"]:
        errors.append("PR14 revert must not be called deliberate")

    r15 = by_no[15]
    if r15["missing_files"] != ["features/force-push-only.txt"]:
        errors.append(f"PR15 missing want [features/force-push-only.txt] got {r15['missing_files']}")
    if r15["mergedness_agrees"]:
        errors.append("PR15 GitHub merged_at vs reachability should disagree")
    if r15["deliberate"]:
        errors.append("PR15 disagreement must not be called deliberate")
    if r15["loss"] != "accidental-force-push-or-unreachable-merge":
        errors.append(f"PR15 loss={r15['loss']}")
    return errors


def run_world() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    tmp = Path(tempfile.mkdtemp(prefix="aud0003-fix-"))
    try:
        world = build_fixture(tmp)
        census = census_fixture(world)
        control = both_states_control(world)
        live = live_owner_attempt(repo_root())
        world = dict(world)
        world["repo"] = "<temp-fixture-removed-after-measure>"
        return world, census, control, live
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
