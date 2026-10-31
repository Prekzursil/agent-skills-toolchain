#!/usr/bin/env python
"""projid — the UNIFIED repo-identity resolver (per-project-intelligence keystone).

WHY THIS EXISTS (fixes a documented bug): the event-ledger keys each project by a
*cwd*-hash slug (``ledger._slug`` = ``basename + sha256(cwd)[:8]``). The same repo opened
from two worktrees, two case-variant paths (``Documents/GitHub`` vs ``Documents/github``),
or a sub-directory therefore lands in DIFFERENT shards — e.g. Reframe fragmented into 5
shards — so "last time in this project we…" can no longer recall across them.

continuous-learning-v2 already solved identity the right way: it keys by a hash of the
git *remote* (portable across machines & worktrees). This module LIFTS that detection
chain into one shared, dependency-free (stdlib-only) place so both the ledger AND CL-v2
can import ONE resolver and agree on identity.

canonical_id is byte-compatible with CL-v2's existing 12-hex ids for the dominant case
(a credential-free https/ssh remote): ``sha256(remote)[:12]``. Normalization is
deliberately MINIMAL — credential stripping only (mirrors detect-project.sh) — because
stripping ``.git`` / lowercasing would change every existing id and orphan CL-v2's stores.

Precedence for the canonical identity source (highest first):
  0. ``<root>/.claude/project-id``  — explicit pin / escape hatch (treat a sub-dir as its
     own project, or pin a custom id).
  1. normalized ``git remote get-url origin`` — unifies all worktrees & sub-dirs of a repo.
  2. ``git rev-parse --show-toplevel`` path — a git repo with no remote.
  3. cwd (raw string) — a non-git directory (reproduces the legacy slug => ZERO churn).

``CLAUDE_PROJECT_DIR`` (if set and a real dir) selects the *root* used for steps 0-2.

Everything here is best-effort and FAIL-OPEN: any git/FS error degrades to the next
precedence rung; callers never crash because identity could not be resolved.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

# Where CL-v2 keeps per-project stores; we reproduce its id so adoption is a no-op.
HOMUNCULUS_PROJECTS = Path.home() / ".claude" / "homunculus" / "projects"
_GIT_TIMEOUT = 5
_ID_LEN = 12  # CL-v2 uses sha256(...)[:12]
_SLUG_HASH_LEN = 8  # event-ledger readable slug uses an 8-hex suffix
_CRED_RE = re.compile(r"://[^@/]+@")  # https://user:tok@host -> https://host


@dataclass(frozen=True)
class ProjId:
    """A stable project identity. ``canonical_id`` is the same for every worktree /
    sub-dir / case-variant path of one repo."""

    canonical_id: str  # 12-hex, CL-v2 compatible
    display_name: str  # human label (repo name, stable across worktrees)
    worktree_path: str  # the actual working directory passed in (absolute)
    source: str  # which precedence rung won: pin|remote|toplevel|cwd
    remote: str | None  # normalized remote url (creds stripped) or None
    toplevel: str | None  # git toplevel path or None
    legacy_id: str | None  # id under the RAW (un-normalized) source, if it differs

    def as_dict(self) -> dict:
        return asdict(self)


def _run_git(cwd: str, *args: str) -> str | None:
    """Run a git command in ``cwd``; return stripped stdout or None. Never raises."""
    try:
        out = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if out.returncode == 0:
            val = out.stdout.strip()
            return val or None
    except Exception:
        pass
    return None


def _norm_remote(url: str) -> str:
    """Minimal, compatibility-safe normalization: strip embedded credentials only.

    Mirrors detect-project.sh (``sed -E 's|://[^@]+@|://|'``). We intentionally do NOT
    strip a trailing ``.git``, lowercase, or drop a trailing slash — those would change
    every existing CL-v2 id (which hashes the raw remote) and orphan its stores.
    """
    return _CRED_RE.sub("://", url.strip())


def _name_from_remote(remote: str) -> str | None:
    """Derive a stable repo name from a remote url (basename minus a trailing .git).

    Stable across worktrees: a worktree dir may be ``Reframe-electron`` while the repo
    is ``Reframe`` — the remote basename gives the canonical project name."""
    s = remote.rstrip("/")
    s = re.sub(r"\.git$", "", s)
    # handle scp-like (git@host:owner/repo) and url (…/owner/repo) forms
    tail = re.split(r"[/:]", s)[-1] if s else ""
    return tail or None


def _hash12(s: str) -> str:
    # sha256 (not md5) per CWE-327, even though this is a non-crypto identity slug.
    return hashlib.sha256(s.encode("utf-8", "replace")).hexdigest()[:_ID_LEN]


def _safe_name(name: str, limit: int = 40) -> str:
    return (
        "".join(c if c.isalnum() or c in "-_." else "-" for c in (name or "root"))[
            :limit
        ]
        or "root"
    )


def _pin(root: str) -> str | None:
    """Explicit override: ``<root>/.claude/project-id`` (first line, validated). Lets a
    user force a sub-dir to be its own project, or pin a shared id across machines."""
    try:
        f = Path(root) / ".claude" / "project-id"
        if f.is_file():
            val = (
                f.read_text(encoding="utf-8", errors="replace")
                .strip()
                .splitlines()[0]
                .strip()
            )
            if val and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", val):
                return val
    except Exception:
        pass
    return None


def _root_for(cwd: str) -> str:
    """The root used for identity lookups: CLAUDE_PROJECT_DIR (if a real dir) else cwd."""
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        try:
            if Path(env).is_dir():
                return env
        except Exception:
            pass
    return cwd


def resolve(cwd: str | None = None) -> ProjId:
    """Resolve a stable project identity for ``cwd`` (defaults to os.getcwd()).

    Pure best-effort: degrades gracefully down the precedence chain; never raises.
    """
    raw_cwd = str(cwd or os.getcwd())
    try:
        worktree = str(Path(raw_cwd).resolve())
    except Exception:
        worktree = raw_cwd
    root = _root_for(raw_cwd)

    # 0. explicit pin
    pin = _pin(root)

    # 1/2. git remote / toplevel (try root, then cwd, so a sub-dir still resolves)
    remote_raw = _run_git(root, "remote", "get-url", "origin") or _run_git(
        raw_cwd, "remote", "get-url", "origin"
    )
    toplevel = _run_git(root, "rev-parse", "--show-toplevel") or _run_git(
        raw_cwd, "rev-parse", "--show-toplevel"
    )
    remote = _norm_remote(remote_raw) if remote_raw else None

    if pin:
        # a 12-hex pin is used verbatim (share an id across machines); any other string is
        # hashed so it is still a valid 12-hex canonical id.
        canonical = pin if re.fullmatch(r"[0-9a-f]{12}", pin) else _hash12(pin)
        return ProjId(
            canonical,
            _safe_name(Path(root).name),
            worktree,
            "pin",
            remote,
            toplevel,
            None,
        )

    if remote:
        canonical = _hash12(remote)
        # legacy_id = id CL-v2 would have computed from the RAW (un-stripped) remote,
        # so a credentialed clone's old store can still be located. None when identical.
        legacy = _hash12(remote_raw) if remote_raw != remote else None
        name = _name_from_remote(remote) or Path(toplevel or root).name
        return ProjId(
            canonical, _safe_name(name), worktree, "remote", remote, toplevel, legacy
        )

    if toplevel:
        canonical = _hash12(toplevel)
        return ProjId(
            canonical,
            _safe_name(Path(toplevel).name),
            worktree,
            "toplevel",
            None,
            toplevel,
            None,
        )

    # 3. non-git: identity == the raw cwd string (matches the legacy ledger slug input)
    canonical = _hash12(raw_cwd)
    return ProjId(
        canonical, _safe_name(Path(raw_cwd).name), worktree, "cwd", None, None, None
    )


def legacy_ledger_slug(cwd: str | None = None) -> str:
    """The PRE-existing event-ledger slug formula (``basename + sha256(rawcwd)[:8]``).

    Kept identical so non-git dirs keep their current shard (zero churn) and so a
    migration can recognise old shard names."""
    p = str(cwd or os.getcwd())
    base = Path(p).name or "root"
    h = hashlib.sha256(p.encode("utf-8", "replace")).hexdigest()[:_SLUG_HASH_LEN]
    return f"{_safe_name(base)}-{h}"


def ledger_slug(cwd: str | None = None) -> str:
    """Readable, *identity-stable* directory name for the event-ledger.

    - git repo (remote/toplevel/pin): ``{display_name}-{canonical_id[:8]}`` — every
      worktree / sub-dir / case-variant of the repo collapses to ONE shard.
    - non-git dir: EXACTLY the legacy formula, so existing shards are untouched.
    """
    raw_cwd = str(cwd or os.getcwd())
    pid = resolve(raw_cwd)
    if pid.source == "cwd":
        return legacy_ledger_slug(raw_cwd)
    return f"{_safe_name(pid.display_name)}-{pid.canonical_id[:_SLUG_HASH_LEN]}"


# ── CL-v2 compatibility shim ───────────────────────────────────────────────────────
def detect_project(cwd: str | None = None) -> dict:
    """continuous-learning-v2-compatible identity dict.

    Returns ``{id, name, root, remote}`` where ``id`` reproduces CL-v2's
    ``sha256(remote if remote else toplevel)[:12]`` for git repos. CL-v2 may
    ``from projid import detect_project`` to share this single resolver; for every
    existing credential-free remote the id is unchanged (verified against the live
    homunculus store). ``global`` is returned when no project context is detected,
    matching CL-v2's fallback.
    """
    raw_cwd = str(cwd or os.getcwd())
    pid = resolve(raw_cwd)
    if pid.source == "cwd":
        # CL-v2 returns "global" when there is no git context and no CLAUDE_PROJECT_DIR.
        env = os.environ.get("CLAUDE_PROJECT_DIR")
        if not (env and Path(env).is_dir()):
            return {
                "id": "global",
                "name": "global",
                "root": "",
                "remote": None,
                "project_dir": str(Path.home() / ".claude" / "homunculus"),
            }
    return {
        "id": pid.canonical_id,
        "name": pid.display_name,
        "root": pid.toplevel or _root_for(raw_cwd),
        "remote": pid.remote,
        "project_dir": str(HOMUNCULUS_PROJECTS / pid.canonical_id),
    }


if __name__ == "__main__":  # pragma: no cover - thin CLI dispatch
    import sys

    # migrate lives in a sibling module to keep this resolver tiny & import-safe.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        import projid_migrate

        sys.exit(projid_migrate.main(sys.argv[2:]))
    # default: print the identity of the cwd (handy for debugging / scripts)
    import json

    print(
        json.dumps(
            resolve(sys.argv[1] if len(sys.argv) > 1 else None).as_dict(), indent=2
        )
    )
