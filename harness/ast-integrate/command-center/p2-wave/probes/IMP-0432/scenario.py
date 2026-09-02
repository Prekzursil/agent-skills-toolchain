#!/usr/bin/env python3
"""Fixture worktrees for IMP-0432 origin-guard probes.

Creates isolated git repos whose origin is set (or omitted) by git command.
Directory names are chosen so a path-string matcher would get the wrong answer
on the spoof fixture.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
GUARD_DIR = REPO / "tools" / "command-center"
if str(GUARD_DIR) not in sys.path:
    sys.path.insert(0, str(GUARD_DIR))

import worktree_origin_guard as G  # noqa: E402

PIN_REL = "command-center/config/pinned-repo-origin.json"
WRONG_ORIGIN = "https://evil.example.invalid/foreign-repo.git"
MARKER = b"PRE-EXISTING-MARKER:do-not-clobber\n"
PAYLOAD = b"IMP-0432-guarded-write-payload\n"


def pin_doc() -> dict:
    return G.load_pin(REPO / PIN_REL)


def pinned_url() -> str:
    return str(pin_doc()["pinned_origin_urls"][0])


def pinned_ssh_alias() -> str:
    """SSH form of the pin: same repo, different spelling. Must PERMIT."""
    url = pinned_url()
    # https://host/path.git -> git@host:path.git
    rest = url.split("://", 1)[1]
    host, _, path = rest.partition("/")
    return f"git@{host}:{path}"


def _git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=G.git_clean_env(),
        timeout=30,
        check=False,
    )


def make_worktree(root: Path, *, origin: str | None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    init = _git(root, ["init"])
    if init.returncode != 0:
        raise RuntimeError(f"git init failed: {init.stderr or init.stdout}")
    _git(root, ["config", "user.email", "imp0432@example.invalid"])
    _git(root, ["config", "user.name", "IMP-0432 fixture"])
    if origin is not None:
        added = _git(root, ["remote", "add", "origin", origin])
        if added.returncode != 0:
            raise RuntimeError(f"git remote add failed: {added.stderr or added.stdout}")
    return root


def attempt_write(worktree: Path, rel: str = "scratch/guarded.txt", data: bytes = PAYLOAD) -> dict:
    target = worktree / rel
    result = G.guarded_write(target, data, pin_doc())
    result["exists_after"] = target.is_file()
    if target.is_file():
        result["bytes_after"] = target.read_bytes()
    else:
        result["bytes_after"] = b""
    return result


def naive_path_string_permit(worktree: Path, pin_token: str) -> bool:
    """Broken matcher: allows a write because the path contains the repo name.

    Probe 2 uses this as the negative control: it would PERMIT the spoof tree.
    The real guard must not.
    """
    return pin_token.lower() in str(worktree).lower()


def naive_missing_origin_allow(worktree: Path) -> bool:
    """Broken matcher: treats missing origin as allow. The real guard must not."""
    got = G.resolve_origin_url(worktree)
    return not got.get("ok")


def build_cases(base: Path) -> list[dict]:
    """Create the evidence worktrees. Returns case records with live write results."""
    pin = pinned_url()
    token = Path(pin.rstrip("/")).name.replace(".git", "")
    cases_meta = [
        {
            "id": "right-repo-https",
            "subdir": "right-https",
            "origin": pin,
            "want_decision": "PERMIT",
            "want_reason": "MATCH",
            "want_write": True,
            "preseed": False,
        },
        {
            "id": "right-repo-ssh-alias",
            "subdir": "right-ssh",
            "origin": pinned_ssh_alias(),
            "want_decision": "PERMIT",
            "want_reason": "MATCH",
            "want_write": True,
            "preseed": False,
        },
        {
            "id": "wrong-repo",
            "subdir": "wrong-foreign",
            "origin": WRONG_ORIGIN,
            "want_decision": "REFUSE",
            "want_reason": "WRONG_REPO",
            "want_write": False,
            "preseed": True,
        },
        {
            "id": "missing-origin",
            "subdir": "no-origin",
            "origin": None,
            "want_decision": "REFUSE",
            "want_reason": "MISSING_ORIGIN",
            "want_write": False,
            "preseed": True,
        },
        {
            "id": "path-spoof-wrong-origin",
            "subdir": f"spoof-{token}",
            "origin": WRONG_ORIGIN,
            "want_decision": "REFUSE",
            "want_reason": "WRONG_REPO",
            "want_write": False,
            "preseed": True,
        },
    ]
    rows = []
    for meta in cases_meta:
        tree = make_worktree(base / meta["subdir"], origin=meta["origin"])
        target = tree / "scratch" / "guarded.txt"
        if meta["preseed"]:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(MARKER)
        result = attempt_write(tree)
        v = result["verdict"]
        rows.append(
            {
                **meta,
                "worktree": str(tree),
                "target": str(target),
                "result": result,
                "table": G.table_row(result),
                "decision": v.get("decision"),
                "reason": v.get("reason"),
                "resolved_origin_url": v.get("resolved_origin_url"),
                "git_command": v.get("git_command"),
                "path_string_used_as_origin": v.get("path_string_used_as_origin"),
                "naive_path_would_permit": naive_path_string_permit(tree, token),
                "naive_missing_would_allow": naive_missing_origin_allow(tree),
                "marker_intact": (not meta["preseed"]) or (target.read_bytes() == MARKER if target.is_file() else False),
            }
        )
    return rows


def evidence_table(rows: list[dict]) -> list[dict]:
    out = []
    for row in rows:
        t = dict(row["table"])
        t["id"] = row["id"]
        t["want_decision"] = row["want_decision"]
        t["observed_decision"] = row["decision"]
        t["marker_intact"] = row["marker_intact"]
        out.append(t)
    return out
