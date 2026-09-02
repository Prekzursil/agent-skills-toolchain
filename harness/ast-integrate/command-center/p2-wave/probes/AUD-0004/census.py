#!/usr/bin/env python3
"""Stash / reflog / dangling-object salvage detectors for AUD-0004.

Probe 1: git fsck --unreachable --dangling.
Probe 2: git stash list plus git stash show --include-untracked --numstat
per entry (a list row is not content).

Fixture git repos live in tempfile only. This module never git-add, stash,
commit, or checkout the ast-integrate worktree.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0004"
OUT_REL = "command-center/audit/AUD-0004-stash-reflog-salvage.json"
SCHEMA_REL = "command-center/schema/audit-inventory.schema.json"

FSCK_LINE = re.compile(
    r"^(dangling|unreachable)\s+(commit|blob|tree|tag)\s+([0-9a-f]{40,64})\b"
)
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")

BASE_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "AUD-0004 Probe",
    "GIT_AUTHOR_EMAIL": "aud-0004@example.test",
    "GIT_COMMITTER_NAME": "AUD-0004 Probe",
    "GIT_COMMITTER_EMAIL": "aud-0004@example.test",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(BASE_GIT_ENV)
    return env


def git_cmd(
    repo: Path,
    args: list[str],
    timeout: int = 60,
    stdin_text: str | None = None,
) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=_env(),
        input=stdin_text,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    rc, out, _err = git_cmd(path, ["rev-parse", "--is-inside-work-tree"])
    return rc == 0 and out.strip() == "true"


def git_version() -> str:
    proc = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, timeout=10
    )
    return (proc.stdout or proc.stderr or "").strip()


def parse_fsck(text: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for line in text.splitlines():
        m = FSCK_LINE.match(line.strip())
        if not m:
            continue
        key = (m.group(1), m.group(2), m.group(3))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "reachability": m.group(1),
                "object_type": m.group(2),
                "sha": m.group(3),
                "line": line.strip(),
            }
        )
    return rows


def fsck_unreachable_dangling(repo: Path) -> dict:
    """Read-only fsck. Does not use --lost-found (that writes .git/lost-found)."""
    cmd = "git fsck --unreachable --dangling"
    if not is_git_repo(repo):
        return {
            "git": False,
            "rc": None,
            "objects": [],
            "object_count": 0,
            "stdout": "",
            "stderr": "not a git repository",
            "command": cmd,
        }
    rc, out, err = git_cmd(repo, ["fsck", "--unreachable", "--dangling"], timeout=120)
    objects = parse_fsck(out + "\n" + err)
    return {
        "git": True,
        "rc": rc,
        "objects": objects,
        "object_count": len(objects),
        "dangling_blob_count": sum(
            1
            for o in objects
            if o["object_type"] == "blob"
            and o["reachability"] in {"dangling", "unreachable"}
        ),
        "dangling_commit_count": sum(
            1
            for o in objects
            if o["object_type"] == "commit"
            and o["reachability"] in {"dangling", "unreachable"}
        ),
        "stdout": out,
        "stderr": err,
        "command": cmd,
    }


def _numstat_files(numstat: str) -> tuple[int, int, int]:
    files = 0
    added = 0
    deleted = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        a, d = parts[0], parts[1]
        files += 1
        if a == "-" or d == "-":
            continue
        try:
            added += int(a)
            deleted += int(d)
        except ValueError:
            continue
    return files, added, deleted


def stash_show_content(repo: Path, ref: str) -> dict:
    rc_u, out_u, err_u = git_cmd(
        repo, ["stash", "show", "--include-untracked", "--numstat", ref]
    )
    rc_d, out_d, err_d = git_cmd(repo, ["stash", "show", "--numstat", ref])
    files_u, add_u, del_u = _numstat_files(out_u)
    files_d, _add_d, _del_d = _numstat_files(out_d)
    rc_p3, _out_p3, _err_p3 = git_cmd(repo, ["rev-parse", "--verify", f"{ref}^3"])
    return {
        "ref": ref,
        "include_untracked_numstat": out_u.strip(),
        "default_numstat": out_d.strip(),
        "include_untracked_files": files_u,
        "default_files": files_d,
        "added": add_u,
        "deleted": del_u,
        "content_nonzero": files_u > 0,
        "default_show_hides_untracked_only": files_d == 0 and files_u > 0,
        "has_untracked_parent": rc_p3 == 0,
        "show_include_untracked_rc": rc_u,
        "show_default_rc": rc_d,
        "show_err": (err_u or err_d).strip()[:500],
    }


def stash_census(repo: Path) -> dict:
    cmd = "git stash list + git stash show --include-untracked --numstat"
    if not is_git_repo(repo):
        return {
            "git": False,
            "entries": [],
            "list_count": 0,
            "nonzero_count": 0,
            "zero_content_count": 0,
            "command": cmd,
        }
    _rc, out, err = git_cmd(repo, ["stash", "list"])
    lines = [ln for ln in out.splitlines() if ln.strip()]
    entries = []
    for i, line in enumerate(lines):
        ref = f"stash@{{{i}}}"
        content = stash_show_content(repo, ref)
        entries.append({"ref": ref, "list_line": line, **content})
    return {
        "git": True,
        "stderr": err,
        "list_raw": out,
        "entries": entries,
        "list_count": len(entries),
        "nonzero_count": sum(1 for e in entries if e["content_nonzero"]),
        "zero_content_count": sum(1 for e in entries if not e["content_nonzero"]),
        "command": cmd,
    }


def reflog_census(repo: Path) -> dict:
    if not is_git_repo(repo):
        return {
            "git": False,
            "entry_count": 0,
            "beyond_tip_commits": [],
            "beyond_tip_count": 0,
        }
    rc_all, out_all, err_all = git_cmd(
        repo, ["reflog", "--all", "--date=iso", "--no-abbrev"]
    )
    lines = [ln for ln in out_all.splitlines() if ln.strip()]
    _rc_rl, out_rl, err_rl = git_cmd(
        repo,
        ["rev-list", "--reflog", "--not", "--branches", "--tags", "--remotes"],
    )
    beyond = [ln.strip() for ln in out_rl.splitlines() if SHA_RE.match(ln.strip())]
    return {
        "git": True,
        "entry_count": len(lines),
        "reflog_all_rc": rc_all,
        "reflog_all_err": err_all,
        "beyond_tip_commits": beyond,
        "beyond_tip_count": len(beyond),
        "rev_list_err": err_rl,
        "sample_lines": lines[:12],
        "command": (
            "git reflog --all --date=iso ; "
            "git rev-list --reflog --not --branches --tags --remotes"
        ),
    }


def _init_fixture(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rc, _out, err = git_cmd(root, ["init"])
    if rc != 0:
        raise RuntimeError(f"git init failed: {err}")
    git_cmd(root, ["config", "user.email", "aud-0004@example.test"])
    git_cmd(root, ["config", "user.name", "AUD-0004 Probe"])
    git_cmd(root, ["config", "commit.gpgsign", "false"])
    (root / "tracked.txt").write_text("tracked-v1\n", encoding="utf-8")
    git_cmd(root, ["add", "tracked.txt"])
    rc, _out, err = git_cmd(root, ["commit", "-m", "init"])
    if rc != 0:
        raise RuntimeError(f"git commit failed: {err}")


def store_empty_stash(repo: Path, message: str = "empty-synthetic") -> str:
    rc_h, head, err_h = git_cmd(repo, ["rev-parse", "HEAD"])
    rc_t, tree, err_t = git_cmd(repo, ["rev-parse", "HEAD^{tree}"])
    if rc_h != 0 or rc_t != 0:
        raise RuntimeError(f"rev-parse failed {err_h} {err_t}")
    head, tree = head.strip(), tree.strip()
    rc_i, index, err_i = git_cmd(
        repo,
        ["commit-tree", tree, "-p", head, "-m", f"index on master: {message}"],
    )
    if rc_i != 0:
        raise RuntimeError(f"index commit-tree failed: {err_i}")
    index = index.strip()
    rc_w, wip, err_w = git_cmd(
        repo,
        [
            "commit-tree",
            tree,
            "-p",
            head,
            "-p",
            index,
            "-m",
            f"WIP on master: {message}",
        ],
    )
    if rc_w != 0:
        raise RuntimeError(f"wip commit-tree failed: {err_w}")
    wip = wip.strip()
    rc_s, _out, err_s = git_cmd(repo, ["stash", "store", "-m", message, wip])
    if rc_s != 0:
        raise RuntimeError(f"stash store failed: {err_s}")
    return wip


def stash_both_states() -> dict:
    """Untracked pathspec saves nothing; tracked stash is non-zero; empty list entry is zero-content."""
    tmp = Path(tempfile.mkdtemp(prefix="aud0004-stash-"))
    try:
        _init_fixture(tmp)
        untracked = tmp / "only-untracked.txt"
        untracked.write_text("untracked-payload\n", encoding="utf-8")
        before = stash_census(tmp)
        rc_u, out_u, err_u = git_cmd(
            tmp,
            ["stash", "push", "-m", "untracked-pathspec", "--", "only-untracked.txt"],
        )
        after_u = stash_census(tmp)
        still_on_disk = untracked.is_file()
        saved_nothing = (
            after_u["list_count"] == before["list_count"]
            and still_on_disk
            and after_u["nonzero_count"] == before["nonzero_count"]
        )
        empty_wip = store_empty_stash(tmp, "empty-synthetic")
        after_empty = stash_census(tmp)
        empty_ok = after_empty["zero_content_count"] >= 1
        empty_entries = [e for e in after_empty["entries"] if not e["content_nonzero"]]

        (tmp / "tracked.txt").write_text("tracked-v2\n", encoding="utf-8")
        rc_t, out_t, err_t = git_cmd(tmp, ["stash", "push", "-m", "tracked-change"])
        after_t = stash_census(tmp)
        tracked_ok = after_t["nonzero_count"] >= 1
        tracked_entries = [e for e in after_t["entries"] if e["content_nonzero"]]

        (tmp / "u-only.txt").write_text("u-only-body\n", encoding="utf-8")
        rc_uu, _out_uu, err_uu = git_cmd(
            tmp,
            ["stash", "push", "-u", "-m", "untracked-with-u", "--", "u-only.txt"],
        )
        after_uu = stash_census(tmp)
        u_hidden = any(
            e.get("default_show_hides_untracked_only") for e in after_uu["entries"]
        )
        return {
            "ok": bool(saved_nothing and empty_ok and tracked_ok),
            "untracked_pathspec": {
                "rc": rc_u,
                "stdout": (out_u or "")[-400:],
                "stderr": (err_u or "")[-400:],
                "stash_created": after_u["list_count"] > before["list_count"],
                "file_remained": still_on_disk,
                "saved_nothing": saved_nothing,
                "content_nonzero": False,
                "list_count_before": before["list_count"],
                "list_count_after": after_u["list_count"],
            },
            "empty_list_entry": {
                "wip": empty_wip,
                "zero_content_count": after_empty["zero_content_count"],
                "list_count": after_empty["list_count"],
                "ok": empty_ok,
                "sample_refs": [e["ref"] for e in empty_entries[:2]],
            },
            "tracked_stash": {
                "rc": rc_t,
                "stdout": (out_t or "")[-400:],
                "stderr": (err_t or "")[-400:],
                "nonzero_count": after_t["nonzero_count"],
                "ok": tracked_ok,
                "sample_refs": [e["ref"] for e in tracked_entries[:2]],
                "sample_files": [
                    e["include_untracked_files"] for e in tracked_entries[:2]
                ],
            },
            "include_untracked_flag_needed": {
                "rc": rc_uu,
                "stderr": (err_uu or "")[-300:],
                "default_show_hides_untracked_only": u_hidden,
            },
            "git_version": git_version(),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fsck_both_states() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="aud0004-fsck-"))
    try:
        _init_fixture(tmp)
        _rc_hb, head_blob, err_hb = git_cmd(tmp, ["rev-parse", "HEAD:tracked.txt"])
        head_blob = head_blob.strip()
        payload = "aud-0004-planted-dangling-blob\n"
        rc_w, planted, err_w = git_cmd(
            tmp, ["hash-object", "-w", "--stdin"], stdin_text=payload
        )
        planted = planted.strip()
        fsck = fsck_unreachable_dangling(tmp)
        shas = {o["sha"] for o in fsck["objects"]}
        blob_shas = {
            o["sha"] for o in fsck["objects"] if o["object_type"] == "blob"
        }
        fired = planted in blob_shas
        silent = head_blob not in shas
        return {
            "ok": bool(
                fired
                and silent
                and SHA_RE.match(planted)
                and SHA_RE.match(head_blob)
            ),
            "planted_blob": planted,
            "head_blob": head_blob,
            "fired_on_planted_blob": fired,
            "silent_on_head_blob": silent,
            "fsck_rc": fsck["rc"],
            "object_count": fsck["object_count"],
            "object_shas": sorted(shas),
            "hash_object_rc": rc_w,
            "hash_object_err": err_w,
            "head_blob_err": err_hb,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def bare_pop_mechanism() -> dict:
    """Bare git stash pop applies stash@{0} (newest), which can be unrelated."""
    tmp = Path(tempfile.mkdtemp(prefix="aud0004-pop-"))
    try:
        _init_fixture(tmp)
        (tmp / "tracked.txt").write_text("intended-older\n", encoding="utf-8")
        git_cmd(tmp, ["stash", "push", "-m", "intended-older"])
        (tmp / "tracked.txt").write_text("unrelated-newer\n", encoding="utf-8")
        git_cmd(tmp, ["stash", "push", "-m", "unrelated-newer"])
        listing = stash_census(tmp)
        _rc0, msg0, _e0 = git_cmd(tmp, ["log", "-1", "--format=%s", "stash@{0}"])
        _rc1, msg1, _e1 = git_cmd(tmp, ["log", "-1", "--format=%s", "stash@{1}"])
        newest_is_unrelated = "unrelated-newer" in (msg0 or "")
        older_is_intended = "intended-older" in (msg1 or "")
        return {
            "ok": bool(
                newest_is_unrelated
                and older_is_intended
                and listing["list_count"] == 2
            ),
            "list_count": listing["list_count"],
            "stash0_subject": (msg0 or "").strip(),
            "stash1_subject": (msg1 or "").strip(),
            "bare_pop_would_apply": "stash@{0}",
            "bare_pop_would_apply_subject": (msg0 or "").strip(),
            "incident_log_in_worktree": False,
            "note": (
                "Catalog names a 2026-08-08 bare pop of an unrelated stash. "
                "This worktree has no contemporaneous incident log. Fixture "
                "shows the mechanism: bare pop == stash@{0} == newest."
            ),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def discover_live_repos() -> dict:
    """Bounded owner-repo scan: this worktree and /opt/p2 first-party trees.

    Does not walk $HOME, ~/Documents/GitHub, or ~/.claude.
    """
    skipped = [
        {
            "path": str(Path.home() / "Documents" / "GitHub"),
            "why": (
                "catalog input for sibling units; this wave forbids walking "
                "concurrent-session trees"
            ),
        },
        {
            "path": str(Path.home() / ".claude"),
            "why": "credential-adjacent; wave floor",
        },
        {
            "path": str(Path.home()),
            "why": "home walk would read credential-bearing files",
        },
    ]
    candidates: list[Path] = [REPO]
    opt = Path("/opt/p2")
    if opt.is_dir():
        for child in sorted(opt.iterdir()):
            if child.is_dir():
                candidates.append(child)
    scanned = []
    git_repos: list[str] = []
    not_git: list[str] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        rec = {
            "path": key,
            "exists": path.exists(),
            "is_git": bool(path.exists() and is_git_repo(path)),
        }
        scanned.append(rec)
        if rec["is_git"]:
            git_repos.append(key)
        elif rec["exists"]:
            not_git.append(key)
    return {
        "scanned": scanned,
        "git_repos": git_repos,
        "not_git": not_git,
        "git_repo_count": len(git_repos),
        "skipped": skipped,
        "worktree_is_git": is_git_repo(REPO),
        "worktree": str(REPO),
    }


def census_repo(path: Path) -> dict:
    git = is_git_repo(path)
    rec = {
        "path": str(path),
        "git": git,
        "fsck": fsck_unreachable_dangling(path),
        "stash": stash_census(path),
        "reflog": reflog_census(path),
    }
    if git:
        rec["head"] = git_cmd(path, ["rev-parse", "HEAD"])[1].strip()
    return rec


def live_inventory() -> dict:
    disc = discover_live_repos()
    repos = []
    items: list[dict] = []
    for git_path in disc["git_repos"]:
        rec = census_repo(Path(git_path))
        repos.append(rec)
        for obj in rec["fsck"].get("objects") or []:
            items.append(
                {
                    "kind": f"fsck-{obj['reachability']}-{obj['object_type']}",
                    "id": obj["sha"],
                    "repo": git_path,
                    "recoverable": True,
                    "content_nonzero": None,
                }
            )
        for ent in rec["stash"].get("entries") or []:
            items.append(
                {
                    "kind": "stash",
                    "id": ent["ref"],
                    "repo": git_path,
                    "recoverable": bool(ent["content_nonzero"]),
                    "content_nonzero": bool(ent["content_nonzero"]),
                    "list_line": ent.get("list_line"),
                }
            )
        for sha in rec["reflog"].get("beyond_tip_commits") or []:
            items.append(
                {
                    "kind": "reflog-beyond-tip",
                    "id": sha,
                    "repo": git_path,
                    "recoverable": True,
                    "content_nonzero": None,
                }
            )
    counts = {
        "live_git_repos": disc["git_repo_count"],
        "live_items": len(items),
        "live_stash_entries": sum(1 for i in items if i["kind"] == "stash"),
        "live_stash_nonzero": sum(
            1 for i in items if i["kind"] == "stash" and i.get("content_nonzero")
        ),
        "live_stash_zero_content": sum(
            1
            for i in items
            if i["kind"] == "stash" and i.get("content_nonzero") is False
        ),
        "live_fsck_objects": sum(1 for i in items if str(i["kind"]).startswith("fsck-")),
        "live_reflog_beyond_tip": sum(
            1 for i in items if i["kind"] == "reflog-beyond-tip"
        ),
        "paths_scanned": len(disc["scanned"]),
    }
    return {
        "discovery": disc,
        "repos": repos,
        "items": items,
        "counts": counts,
    }


def headline_public(inv: dict, stash_ctl: dict, fsck_ctl: dict, pop_ctl: dict) -> dict:
    counts = inv["counts"]
    return {
        "live_git_repos": counts["live_git_repos"],
        "live_item_count": counts["live_items"],
        "live_stash_nonzero": counts["live_stash_nonzero"],
        "live_stash_zero_content": counts["live_stash_zero_content"],
        "live_fsck_objects": counts["live_fsck_objects"],
        "live_reflog_beyond_tip": counts["live_reflog_beyond_tip"],
        "worktree_is_git": inv["discovery"]["worktree_is_git"],
        "untracked_pathspec_saved_nothing": stash_ctl["untracked_pathspec"][
            "saved_nothing"
        ],
        "tracked_stash_nonzero": stash_ctl["tracked_stash"]["ok"],
        "empty_stash_list_entry_zero_content": stash_ctl["empty_list_entry"]["ok"],
        "dangling_blob_fired": fsck_ctl["fired_on_planted_blob"],
        "reachable_head_blob_silent": fsck_ctl["silent_on_head_blob"],
        "bare_pop_applies_newest": pop_ctl["ok"],
        "git_version": stash_ctl.get("git_version") or git_version(),
    }


def measure() -> dict:
    stash_ctl = stash_both_states()
    fsck_ctl = fsck_both_states()
    pop_ctl = bare_pop_mechanism()
    inv = live_inventory()
    head = headline_public(inv, stash_ctl, fsck_ctl, pop_ctl)
    ok = bool(
        stash_ctl["ok"]
        and fsck_ctl["ok"]
        and pop_ctl["ok"]
        and stash_ctl["untracked_pathspec"]["saved_nothing"]
        and stash_ctl["tracked_stash"]["ok"]
        and fsck_ctl["fired_on_planted_blob"]
        and fsck_ctl["silent_on_head_blob"]
    )
    return {
        "ok": ok,
        "stash_control": stash_ctl,
        "fsck_control": fsck_ctl,
        "bare_pop": pop_ctl,
        "live": inv,
        "headline": head,
    }
