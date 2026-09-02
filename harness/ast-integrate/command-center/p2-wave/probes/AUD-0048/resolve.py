#!/usr/bin/env python3
"""Probe-2 instrument: resolve action tags to the SHA git ls-remote sees today."""
from __future__ import annotations

import hashlib
import subprocess
from typing import Any

from classify import github_repo

SHA40 = __import__("re").compile(r"^[0-9a-fA-F]{40}$")


def parse_ls_remote(text: str, ref: str) -> dict[str, Any]:
    """Pick the peeled annotated-tag SHA when present, else the tag/head SHA."""
    peeled = None
    direct = None
    heads = None
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        sha, name = parts[0], parts[1]
        if not SHA40.match(sha):
            continue
        if name.endswith("^{}"):
            peeled = sha.lower()
        elif name.endswith(f"refs/tags/{ref}") or name == f"refs/tags/{ref}":
            direct = sha.lower()
        elif name.endswith(f"refs/heads/{ref}") or name == f"refs/heads/{ref}":
            heads = sha.lower()
    sha = peeled or direct or heads
    return {
        "sha": sha,
        "peeled": peeled,
        "direct": direct,
        "heads": heads,
        "resolved": bool(sha),
    }


def ls_remote(repo: str, ref: str, timeout: int = 25) -> dict[str, Any]:
    url = f"https://github.com/{repo}.git"
    specs = [f"refs/tags/{ref}", f"refs/tags/{ref}^{{}}", f"refs/heads/{ref}"]
    try:
        p = subprocess.run(
            ["git", "ls-remote", url, *specs],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "repo": repo,
            "ref": ref,
            "url": url,
            "ok": False,
            "sha": None,
            "error": f"{type(exc).__name__}: {exc}",
            "raw": "",
        }
    parsed = parse_ls_remote(p.stdout or "", ref)
    return {
        "repo": repo,
        "ref": ref,
        "url": url,
        "ok": bool(p.returncode == 0 and parsed["resolved"]),
        "exit_code": p.returncode,
        "sha": parsed["sha"],
        "peeled": parsed["peeled"],
        "direct": parsed["direct"],
        "stderr": (p.stderr or "")[:400],
        "raw": (p.stdout or "")[:800],
        "fingerprint": hashlib.sha256(
            f"git-ls-remote\x1f{url}\x1f{ref}".encode()
        ).hexdigest()[:16],
    }


def resolve_use(rec: dict[str, Any]) -> dict[str, Any]:
    action = rec.get("action") or ""
    ref = rec.get("ref") or ""
    pin = rec.get("pin_class") or ""
    repo = github_repo(action)
    out = {
        "action": action,
        "ref": ref,
        "pin_class": pin,
        "file": rec.get("file"),
        "repo": repo,
        "attempted": False,
        "ok": False,
        "sha": None,
        "skip_reason": None,
    }
    if rec.get("local") or rec.get("kind") == "docker":
        out["skip_reason"] = "not-a-github-action"
        return out
    if pin == "sha-pinned":
        out["skip_reason"] = "already-sha-pinned"
        out["sha"] = ref.lower()
        return out
    if pin not in {"tag-pinned", "branch-pinned", "sha-abbreviated"}:
        out["skip_reason"] = f"pin_class={pin}"
        return out
    if not repo or not ref:
        out["skip_reason"] = "missing-repo-or-ref"
        return out
    out["attempted"] = True
    got = ls_remote(repo, ref)
    out.update(
        {
            "ok": got["ok"],
            "sha": got.get("sha"),
            "url": got.get("url"),
            "stderr": got.get("stderr"),
            "raw": got.get("raw"),
            "fingerprint": got.get("fingerprint"),
            "error": None if got["ok"] else (got.get("error") or got.get("stderr") or "unresolved"),
        }
    )
    return out
