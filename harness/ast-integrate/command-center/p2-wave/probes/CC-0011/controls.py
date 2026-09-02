#!/usr/bin/env python3
"""Four catalog tests_required for CC-0011, all on scratch trees.

Canary bodies live only in tempfile and process memory. They are never written
under the worktree and never returned from this module.
"""
from __future__ import annotations

import os
import secrets
import subprocess
import tempfile
from pathlib import Path

from scanner import (
    PREFIX_ANTHROPIC,
    PREFIX_AWS,
    PREFIX_GITHUB,
    scan_git_history,
    scan_path,
    scan_text,
)

# Anthropic prefix + 40-char urlsafe body (hyphen/underscore allowed by the rule).
def _anthropic_canary() -> str:
    return PREFIX_ANTHROPIC + secrets.token_urlsafe(30)[:40]


def _github_canary() -> str:
    return PREFIX_GITHUB + secrets.token_hex(18)  # 36 hex chars


def detector_control() -> dict:
    """A planted synthetic token in a scratch file must be found by both engines."""
    token = _anthropic_canary()
    with tempfile.TemporaryDirectory(prefix="cc0011-det-") as td:
        root = Path(td)
        planted = root / "scratch.env"
        planted.write_text(
            f"# synthetic detector-control; not a live credential\n"
            f"ANTHROPIC_API_KEY={token}\n",
            encoding="utf-8",
        )
        pattern_hits = scan_path(
            planted, repo=root, scope="fixture-detector", engines=("pattern",)
        )
        entropy_hits = scan_path(
            planted, repo=root, scope="fixture-detector", engines=("entropy-name",)
        )
        both = scan_path(planted, repo=root, scope="fixture-detector")
    found_pattern = any(
        h.prefix == PREFIX_ANTHROPIC and h.byte_length == len(token) for h in pattern_hits
    )
    found_entropy = any(
        h.engine == "entropy-name" and h.variable_name == "ANTHROPIC_API_KEY" for h in entropy_hits
    )
    # Body must not leak into Hit fields.
    leaked = any(token in str(h.as_public()) for h in both)
    return {
        "id": "detector-control",
        "found_by_pattern": found_pattern,
        "found_by_entropy_name": found_entropy,
        "both_engines": found_pattern and found_entropy,
        "hit_count_pattern": len(pattern_hits),
        "hit_count_entropy": len(entropy_hits),
        "body_leaked_into_hit": leaked,
        "pass": found_pattern and found_entropy and not leaked,
    }


def false_positive_control() -> dict:
    """A bare zero-entropy prefix with no secret body must NOT fire."""
    with tempfile.TemporaryDirectory(prefix="cc0011-fp-") as td:
        root = Path(td)
        bare = root / "prefixes-only.txt"
        bare.write_text(
            "documented prefixes with no body\n"
            f"ANTHROPIC_API_KEY={PREFIX_ANTHROPIC}\n"
            f"GITHUB_TOKEN={PREFIX_GITHUB}\n"
            f"AWS_ACCESS_KEY_ID={PREFIX_AWS}\n"
            "sk-ant-\n"
            "ghp_\n"
            "AKIA\n",
            encoding="utf-8",
        )
        hits = scan_path(bare, repo=root, scope="fixture-false-positive")
    return {
        "id": "false-positive-control",
        "hit_count": len(hits),
        "rules": sorted({h.rule for h in hits}),
        "pass": len(hits) == 0,
    }


def known_clean_sentinel() -> dict:
    """A file with no secrets must score 0 hits."""
    with tempfile.TemporaryDirectory(prefix="cc0011-clean-") as td:
        root = Path(td)
        clean = root / "notes.md"
        clean.write_text(
            "# Known-clean sentinel\n"
            "This file discusses secret *prefixes* such as sk-ant- and ghp_\n"
            "and the AWS marker AKIA. Those are documented prefixes, not bodies.\n"
            "sha256 of empty: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855\n"
            "variable names: API_KEY, TOKEN, SECRET — no values.\n",
            encoding="utf-8",
        )
        hits = scan_path(clean, repo=root, scope="fixture-known-clean")
    return {
        "id": "known-clean-sentinel",
        "hit_count": len(hits),
        "pass": len(hits) == 0,
    }


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "cc-0011"
    env["GIT_AUTHOR_EMAIL"] = "cc-0011@example.invalid"
    env["GIT_COMMITTER_NAME"] = "cc-0011"
    env["GIT_COMMITTER_EMAIL"] = "cc-0011@example.invalid"
    return subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=cc-0011",
            "-c",
            "user.email=cc-0011@example.invalid",
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def historical_scope() -> dict:
    """Deleted leak must still be found in committed history, not the working tree."""
    token = _github_canary()
    with tempfile.TemporaryDirectory(prefix="cc0011-hist-") as td:
        repo = Path(td)
        _git(repo, "init", "-q")
        leak = repo / "command-center" / "leaked.env"
        leak.parent.mkdir(parents=True)
        leak.write_text(f"GITHUB_TOKEN={token}\n", encoding="utf-8")
        _git(repo, "add", "command-center/leaked.env")
        _git(repo, "commit", "-q", "-m", "plant canary")
        leak.unlink()
        _git(repo, "add", "-u", "command-center/leaked.env")
        _git(repo, "commit", "-q", "-m", "delete canary — deleting is not sufficient")
        wt_hits = scan_path(
            repo / "command-center",
            repo=repo,
            scope="fixture-history-worktree",
            engines=("pattern",),
        )
        hist_hits = scan_git_history(
            repo,
            pathspec="command-center",
            label_path="command-center/leaked.env",
            scope="fixture-history",
        )
        worktree_clean = len(wt_hits) == 0
        history_found = any(
            h.prefix == PREFIX_GITHUB and h.commit and h.byte_length == len(token)
            for h in hist_hits
        )
        leaked = any(token in str(h.as_public()) for h in list(wt_hits) + list(hist_hits))
    return {
        "id": "historical-scope",
        "worktree_hits_after_delete": len(wt_hits),
        "history_hits": len(hist_hits),
        "worktree_silent_after_delete": worktree_clean,
        "history_found_deleted_token": history_found,
        "body_leaked_into_hit": leaked,
        "pass": worktree_clean and history_found and not leaked,
    }


def run_all() -> dict:
    results = [
        detector_control(),
        false_positive_control(),
        known_clean_sentinel(),
        historical_scope(),
    ]
    return {
        "all_pass": all(r["pass"] for r in results),
        "results": results,
    }


if __name__ == "__main__":
    import json

    doc = run_all()
    print(json.dumps({k: v for k, v in doc.items() if k != "results"}, indent=2))
    for r in doc["results"]:
        print(f"{r['id']}: pass={r['pass']}")
    raise SystemExit(0 if doc["all_pass"] else 1)
