#!/usr/bin/env python
"""Stop hook -- git hygiene: surface work that is NOT safely in version control.

WHAT IT ANSWERS, at session end:
  1. Did I author anything under the LIVE harness trees (~/.claude, ~/.agents, ~/.local/bin)
     that `scripts/sync-from-live.ps1` would carry into the repo but that is not there yet?
     Before that script existed, 462 files / 2.73 MB of harness work were ARCHITECTURALLY
     orphaned -- the repo shipped only repo->live sync, so live-authored work could never
     reach version control at all.
  2. Are any of MY repos holding uncommitted work, unpushed commits, or no upstream?
  3. Has the toolchain repo's OWN documentation rotted -- markdown links pointing at a file
     that no longer exists, or editor/agent backup cruft (*.bak-*, *.orig, *-OLD.md) that got
     committed? This is the docs-cleaning dimension; it scans the repo, never the live tree.
  4. Is a whole SKILL or MCP SERVER deployed live but missing from the repo? File-level drift
     (1) misses this: ~/.claude/skills was never in the sync map, so a skill there could never
     reach the repo, and a registered MCP server's launcher could sit uncommitted. This
     dimension names the offenders -- a missing skill/server is too load-bearing for a count.

WHY THE CLASSIFIER IS THE PRODUCT (measured on this box, 2026-07-18):
    329 git repositories discovered      175 dirty      111 without an upstream
Of those, the overwhelming majority are SOMEONE ELSE'S and dirt in them is the expected
steady state:
    258  third-party clones under ~/.claude/plugins/**       (the CLI's own plugin cache)
     20  detached-HEAD scratch worktrees under ~/.claude/agent-worktrees/*  (all 0 dirty)
      8  no-remote `temp_subdir_*.clone` husks in that cache (see PR2-glob-enametoolong)
    ~37  dirty files across insta-mcp / hexstrike-ai / mcp_agent_mail / whatsapp-mcp / ...
A hook that reports those emits ~175 lines of noise and gets disabled within a day, which is
strictly worse than no hook. So this file spends its complexity on TELLING YOURS FROM
VENDORED, not on scanning.

COST (measured, and the reason for the shape of the code): a first version issued SIX git
subprocesses per repo and took 1,322 ms/repo -- 63 s for 48 repos, unusable in a Stop hook.
`git status --porcelain=v2 --branch` returns oid/head/upstream/ahead/behind AND the dirty
entries in ONE call, so the probe is now 2 spawns per repo, run 8-wide. The live-tree walk
prunes with os.walk instead of filtering rglob output after the fact.

Hook LAW (AGENTS.md §6): external signal (git) the model cannot fake; INJECT additionalContext;
always exit 0. Blocking a Stop on uncommitted work would be maddening and is explicitly against
the contract -- there is no code path here that returns 2.

Opt-out:  GIT_HYGIENE=off  in env, or  hooks/git-hygiene/.disabled
Tuning:   GIT_HYGIENE_OWNER   github owner treated as YOURS        (default: Prekzursil)
          GIT_HYGIENE_ROOTS   os.pathsep-separated scan roots; set-but-empty = scan nothing
          GIT_HYGIENE_SYNC    'off' skips the live-tree drift half
          GIT_HYGIENE_DOCS    'off' skips the docs-hygiene half
          GIT_HYGIENE_COVERAGE 'off' skips the skills/MCP coverage half
          GIT_HYGIENE_BASE    committed ref coverage compares against  (default: origin/main)
          GIT_HYGIENE_REPO    toolchain repo root for the drift + docs + coverage comparison
          GIT_HYGIENE_BUDGET  seconds of wall clock the whole check may spend (default 5)
          GIT_HYGIENE_LIVE_STATE  os.pathsep-separated globs whose dirty state is CORRECT
                              and must not be reported (default: accounts.json)
          GIT_HYGIENE_NO_SKIP=1   disable the live-state filter entirely (audit the skip)
"""

from __future__ import annotations

import concurrent.futures as _fut
import fnmatch
import json
import os
import posixpath
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from urllib.parse import unquote

THIS = Path(__file__).resolve().parent

# ---- ownership classes -----------------------------------------------------------------
YOURS = "YOURS"  # you own it: report real risk
VENDORED = "VENDORED"  # someone else's code sitting on your disk: never report
NO_REMOTE = "NO-REMOTE"  # yours, but it exists nowhere else in the world
EPHEMERAL = "EPHEMERAL"  # agent scratch worktree, auto-reclaimed: never report

# ---- severity: LOWER SORTS FIRST, ordered by how much work a disk failure would destroy --
SEV_NO_REMOTE = 0  # exists only on this disk
SEV_DIRTY_NO_UPSTREAM = 1  # uncommitted AND the branch was never pushed
SEV_UNPUSHED = 2  # committed locally, absent from the remote
SEV_DIRTY = 3  # uncommitted, but the branch is already on the remote
SEV_NO_UPSTREAM = 4  # clean, but this branch has never been pushed

MAX_LINES = (
    20  # a hook nobody reads is a hook nobody keeps; 4 dimensions now share the cap
)
MAX_ROWS = 8
# The repo half's truncation FLOOR. It is the only section whose height scales with the
# finding count, so it is budgeted against the lines the sections below it need (see
# build_message) -- but never below this, or a large docs section would starve the repo half
# in turn: the same defect, mirrored. It also keeps a negative budget away from the row
# slice, where reportable[:-n] would silently keep the WRONG rows and print a suppressed
# count that does not match them.
MIN_ROWS = 2
WORKERS = 8


@dataclass(frozen=True)
class Config:
    owner: str = "Prekzursil"
    # CLASSIFICATION markers -- matched against the lowercased, forward-slashed path.
    vendor_markers: tuple = (
        "/.claude/plugins/",
        "/.local/opt/",
        "/node_modules/",
        "/site-packages/",
        "/vendor/",
        "/third_party/",
    )
    ephemeral_markers: tuple = ("/.claude/agent-worktrees/", "/.claude/worktrees/")
    # WALK pruning -- purely a cost control. Kept SEPARATE from vendor_markers on purpose:
    # pruning a path also makes its nested repos undiscoverable, so anything we still want
    # to *classify* must remain walkable. Only the 258-repo plugin cache earns a prune.
    prune_markers: tuple = ("/.claude/plugins/",)
    exclude_dirs: frozenset = field(
        default_factory=lambda: frozenset(
            {
                ".git",
                "node_modules",
                "__pycache__",
                ".venv",
                "venv",
                "site-packages",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
                ".tox",
                "dist",
                "build",
                ".next",
                "target",
                ".gradle",
            }
        )
    )
    # Mirrors sync-from-live.ps1's $ExcludeFilePatterns. '*.bak' alone is NOT enough: the
    # live tree carries suffixed forms like '.bak-fleet-20260713'; the narrow pattern once
    # let 32 files of agent backup cruft into a commit.
    exclude_patterns: tuple = (
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dll",
        "*.exe",
        "*.egg-info",
        "*.log",
        "*.tmp",
        ".DS_Store",
        "Thumbs.db",
        "*.sqlite",
        "*.sqlite3",
        "*.db",
        "*.bak",
        "*.bak-*",
        "*.bak.*",
        "*.orig",
        "*.rej",
        "*~",
        "*.old",
        "*.save",
        # Hook RUNTIME STATE that .gitignore already excludes. This walker does not consult
        # .gitignore, so without these two the scanner reports files git is already ignoring
        # as "drift" that a sync should carry -- drift that can never be resolved by
        # committing, because committing them is exactly what .gitignore forbids. Measured
        # 2026-07-20: git-hygiene/.last-run (this hook own throttle stamp) and
        # local-tui-reminder/.shown-2026-07-20 were 2 of a reported 169.
        ".last-run",
        ".shown-*",
    )
    max_depth: int = 2
    # Measured end-to-end on this box: 3.7 s warm, 5.6 s cold. 8 s leaves headroom so a cold
    # cache does not truncate the report; the hook declares truncation when it does happen.
    budget_s: float = 8.0
    cap: int = 40_000

    # ---- docs-hygiene dimension ----------------------------------------------------------
    # Extensions treated as PROSE for the broken-link scan.
    doc_exts: tuple = (".md", ".markdown")
    # Committed editor/agent leftovers. Distinct from exclude_patterns above, which keeps
    # this cruft OUT of a sync; these patterns find the copies that already got IN.
    doc_cruft_patterns: tuple = (
        "*.bak",
        "*.bak-*",
        "*.bak.*",
        "*.orig",
        "*.rej",
        "*~",
        "*.old",
        "*.save",
        "*-OLD.md",
        "*-old.md",
        "*.md.txt",
        "* copy.md",
        "*.copy.md",
    )
    # Measured on this repo: 3,103 tracked docs / 17.6 MB read+scanned in 590-742 ms.
    # The cap is ~30% headroom over that, so growth degrades to "truncated" not "slow".
    docs_cap: int = 4_000
    # Prefixes skipped by the broken-link scan (fnmatch on the repo-relative path).
    # These trees are NOT authoritative prose:
    #   platform/routing/fixtures/  -- synthetic skill stubs for routing tests
    #   **/vendor/                  -- third-party trees we do not own
    #   agent-self/config/          -- incomplete harness mirror (paths resolve elsewhere)
    #   .agents/skills/             -- deploy mirror of skills/; dual-write makes the same
    #                                 relative link correct under skills/ and wrong here
    #                                 (skills/X -> ../../guides vs .agents/skills/X ->
    #                                 ../../../guides). Scanning both double-counts.
    #   harness-sota-*-corpus/      -- dated audit dumps, not living docs
    doc_skip_globs: tuple = (
        "platform/routing/fixtures/*",
        "*/vendor/*",
        "agent-self/config/*",
        ".agents/skills/*",
        "harness-sota-*-corpus/*",
    )

    # ---- coverage dimension (skills + MCP servers deployed-but-not-committed) -------------
    # LIVE skill roots (each top-level dir is one skill). ~/.claude/skills was the measured
    # blind spot: it had never been in the sync map, so a skill living only there could never
    # reach the repo. Both roots are scanned; a name in either counts as "live".
    live_skill_roots: tuple = (".claude/skills", ".agents/skills")
    # REPO trees that COVER a skill. A live skill present in ANY of these is committed; only a
    # skill absent from ALL of them is flagged. Avoids double-counting a skill in two trees.
    repo_skill_trees: tuple = ("skills", ".agents/skills", "skills-claude-only")
    mcp_manifest: str = ".mcp.json"  # relative to HOME
    coverage_name_cap: int = 6  # names shown in the message before "+N more"


@dataclass(frozen=True)
class RepoState:
    path: str
    origin: str = ""
    has_remote: bool = False
    branch: str = ""  # "" means DETACHED HEAD
    upstream: str = ""
    dirty: int = 0
    # Dirty entries filtered out as LIVE STATE (see LIVE_STATE_GLOBS). Carried so the
    # suppression can be printed rather than silently applied.
    dirty_excluded: int = 0
    ahead: int = 0
    unborn: bool = False  # `git init` with no commit yet -- rev-parse HEAD fails here
    is_worktree: bool = False
    nested_in: str = ""  # path of the enclosing repo, if this one sits inside another


@dataclass(frozen=True)
class Verdict:
    path: str
    name: str
    ownership: str
    report: bool
    severity: int
    detail: str
    action: str


@dataclass(frozen=True)
class CoverageReport:
    """A deployed harness component (a live skill, a registered MCP server) that is NOT in
    version control. NAME-bearing on purpose: 'skills 14' is skate-past-able, but naming the
    skill that would vanish on a disk failure is not. This is the drift detector's answer to
    its measured blind spots -- a whole skill or MCP slipping out of the repo unnoticed."""

    area: str  # "skills" | "mcp"
    missing: int = 0
    names: tuple = ()  # the offenders, sorted, capped for the message
    total_names: int = 0  # full count so the message can say "+N more"
    stood_down: bool = False  # coverage could not be determined -> reported nothing

    @property
    def actionable(self) -> int:
        return self.missing


@dataclass(frozen=True)
class DocsReport:
    """Documentation that has rotted: links to files that are gone, and committed cruft."""

    broken_links: int = 0
    cruft_files: int = 0
    scanned: int = 0
    truncated: bool = False  # the budget or the cap expired: counts are a FLOOR
    link_examples: tuple = ()  # up to 3 "doc -> missing target" strings
    cruft_examples: tuple = ()  # up to 3 repo-relative paths
    judged: bool = True  # False = the discriminator was unavailable, links NOT scanned

    @property
    def actionable(self) -> int:
        return self.broken_links + self.cruft_files


@dataclass(frozen=True)
class DriftReport:
    area: str
    live_only: int  # exists live, absent from the repo -> sync would ADD it
    differing: int  # exists in both, sizes differ    -> sync would UPDATE it
    actionable: int  # live_only + differing
    scanned: int
    truncated: bool  # the budget expired: this count is a FLOOR, not a total


# ------------------------------------------------------------------------------------------
# git plumbing
# ------------------------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=20
        )
        return (r.stdout or "").strip() if r.returncode == 0 else ""
    except Exception:  # noqa: BLE001 - a git that hangs or is missing must not break Stop
        return ""


def _owner_of(origin: str) -> str:
    """Owner segment of a remote URL, or '' if it cannot be parsed.

    Parsed rather than substring-matched on purpose: `'prekzursil' in origin` also matches
    https://github.com/someoneelse/prekzursil-fork.git, which is emphatically not yours.
    """
    if not origin:
        return ""
    s = origin.strip().rstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    if "://" in s:
        s = s.split("://", 1)[1]
    if "@" in s.split("/", 1)[0]:  # git@github.com:owner/repo  or  ssh://git@host/
        s = s.split("@", 1)[1]
    s = s.replace(":", "/")
    parts = [p for p in s.split("/") if p]
    return parts[-2] if len(parts) >= 2 else ""


# Paths that are LIVE STATE, not work in progress: dirty is their correct resting state
# and the hook's own advice ("commit, then push") must never be followed for them. The
# measured case is the credential-rotation pool -- `tools/mcp/*/accounts.json` in the
# canonical toolchain checkout is modified on every rotation and a standing owner
# constraint forbids staging it, so before this filter the hook flagged that repo on every
# single turn forever with a remedy that is prohibited. A guard that cannot reach green
# gets skipped, and the cost lands on the turn when one of its flags is real.
#
# Suppression is AUDITABLE, not silent: the excluded count is carried on RepoState and
# printed, and GIT_HYGIENE_NO_SKIP=1 disables the filter entirely.
LIVE_STATE_GLOBS = ("accounts.json",)


def _live_state_globs() -> tuple[str, ...]:
    raw = os.environ.get("GIT_HYGIENE_LIVE_STATE")
    if raw is None:
        return LIVE_STATE_GLOBS
    return tuple(g for g in raw.split(os.pathsep) if g.strip())


def _v2_path(line: str) -> str:
    """Extract the path from one porcelain=v2 entry.

    The record shapes differ and getting this wrong reintroduces the false positive
    through a side door -- a RENAMED or UNTRACKED copy of the same file. Shapes:
      `1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>`             -> last field
      `2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <Xscore> <path>\t<orig>` -> field 10, pre-TAB
      `u <XY> <sub> <m1> <m2> <m3> <mW> <h1> <h2> <h3> <path>`   -> last field
      `? <path>` / `! <path>`                                    -> rest of line
    """
    kind = line[0]
    if kind in "?!":
        return line[2:].strip()
    parts = (
        line.split(" ", 9) if kind == "2" else line.split(" ", 10 if kind == "u" else 8)
    )
    if kind == "2":
        return parts[9].split("\t", 1)[0].strip() if len(parts) > 9 else ""
    idx = 10 if kind == "u" else 8
    return parts[idx].strip() if len(parts) > idx else ""


def _is_live_state(path: str, globs: tuple[str, ...]) -> bool:
    if not path:
        return False
    norm = path.replace("\\", "/")
    base = posixpath.basename(norm)
    return any(
        fnmatch.fnmatch(norm, g) or fnmatch.fnmatch(base, g) or norm.endswith("/" + g)
        for g in globs
    )


def _parse_status_v2(out: str):
    """Parse `git status --porcelain=v2 --branch`.

    One call yields oid (unborn?), head (detached?), upstream, ahead/behind and every
    dirty entry. Replaces six separate `git` spawns -- the difference between 1,322 ms
    and ~170 ms per repo, measured.

    Returns (branch, upstream, ahead, dirty, unborn, dirty_excluded). `dirty` counts only
    entries that are real work at risk; `dirty_excluded` counts the live-state paths
    filtered out, so the suppression is visible rather than inferred.
    """
    branch, upstream, ahead, dirty, unborn = "", "", 0, 0, False
    excluded = 0
    globs = () if os.environ.get("GIT_HYGIENE_NO_SKIP") else _live_state_globs()
    for line in out.splitlines():
        if not line:
            continue
        if line[0] != "#":
            if globs and _is_live_state(_v2_path(line), globs):
                excluded += 1
            else:
                dirty += 1
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        key, val = parts[1], parts[2]
        if key == "branch.oid":
            unborn = val == "(initial)"
        elif key == "branch.head":
            branch = "" if val == "(detached)" else val
        elif key == "branch.upstream":
            upstream = val
        elif key == "branch.ab" and len(parts) >= 4:
            try:
                ahead = int(parts[2].lstrip("+"))
            except ValueError:
                ahead = 0
    return branch, upstream, ahead, dirty, unborn, excluded


def read_repo_state(path) -> RepoState | None:
    p = Path(path)
    dot = p / ".git"
    if not dot.exists():
        return None
    branch, upstream, ahead, dirty, unborn, excluded = _parse_status_v2(
        _git(p, "status", "--porcelain=v2", "--branch")
    )
    # One call for every remote URL: gives has_remote AND origin without a second spawn.
    remotes = _git(p, "config", "--get-regexp", r"^remote\..*\.url")
    origin = ""
    for line in remotes.splitlines():
        bits = line.split(None, 1)
        if len(bits) == 2 and bits[0] == "remote.origin.url":
            origin = bits[1].strip()
    return RepoState(
        path=str(p),
        origin=origin,
        has_remote=bool(remotes.strip()),
        branch=branch,
        upstream=upstream,
        dirty=dirty,
        dirty_excluded=excluded,
        ahead=ahead,
        unborn=unborn,
        is_worktree=dot.is_file(),
    )


# ------------------------------------------------------------------------------------------
# classification -- ORDER IS LOAD-BEARING: position beats provenance
# ------------------------------------------------------------------------------------------
def _norm(path: str) -> str:
    return path.replace("\\", "/").lower()


def _matches(path: str, markers) -> bool:
    n = _norm(path)
    return any(m.lower() in n for m in markers)


def classify(state: RepoState, cfg: Config) -> Verdict:
    name = Path(state.path).name

    def v(ownership, report, severity=SEV_DIRTY, detail="", action=""):
        return Verdict(
            path=state.path,
            name=name,
            ownership=ownership,
            report=report,
            severity=severity,
            detail=detail,
            action=action,
        )

    # 1. Agent scratch worktrees. 20 measured, all detached, all clean -- and they are
    #    reclaimed automatically, so nothing here is ever "abandoned".
    if _matches(state.path, cfg.ephemeral_markers):
        return v(EPHEMERAL, False, detail="agent scratch worktree")

    # 2/3. POSITION FIRST. A clone nested inside another repo, or living in a dependency /
    #      plugin cache, is vendored REGARDLESS of what its origin says -- 8 measured husks
    #      have no remote at all, and grading them on provenance would drop them into the
    #      highest-severity bucket and dominate the report.
    if state.nested_in:
        return v(
            VENDORED, False, detail=f"clone nested inside {Path(state.nested_in).name}"
        )
    if _matches(state.path, cfg.vendor_markers):
        return v(VENDORED, False, detail="third-party tree")

    # 4. Provenance.
    if state.has_remote and _owner_of(state.origin).lower() != cfg.owner.lower():
        return v(
            VENDORED, False, detail=f"origin owned by {_owner_of(state.origin) or '?'}"
        )

    ownership = YOURS if state.has_remote else NO_REMOTE
    detached = state.branch == ""
    where = f"on {state.branch}" if state.branch else "at a detached HEAD"

    excl = (
        f" ({state.dirty_excluded} live-state path(s) excluded)"
        if state.dirty_excluded
        else ""
    )

    # Nothing uncommitted and nothing unique here: a detached HEAD or an empty `git init`
    # cannot lose work it does not have. (~/Documents/Misc is exactly the latter.)
    if state.dirty == 0 and (detached or (state.unborn and ownership == NO_REMOTE)):
        return v(ownership, False, detail="nothing at risk" + excl)

    if ownership == NO_REMOTE:
        what = (
            f"{state.dirty} uncommitted file(s)"
            if state.dirty
            else "commits exist only here"
        )
        return v(
            NO_REMOTE,
            True,
            SEV_NO_REMOTE,
            f"NO REMOTE AT ALL -- {what}; this work exists nowhere else",
            "create a remote and push: gh repo create --source . --private --push",
        )

    if state.dirty and not state.upstream:
        return v(
            YOURS,
            True,
            SEV_DIRTY_NO_UPSTREAM,
            f"{state.dirty} uncommitted file(s) {where}, and the branch has no upstream{excl}",
            "commit, then: git push -u origin HEAD",
        )
    if state.ahead > 0:
        extra = f" (+{state.dirty} uncommitted)" if state.dirty else ""
        return v(
            YOURS,
            True,
            SEV_UNPUSHED,
            f"{state.ahead} unpushed commit(s) {where}{extra}",
            "git push",
        )
    if state.dirty:
        return v(
            YOURS,
            True,
            SEV_DIRTY,
            f"{state.dirty} uncommitted file(s) {where}{excl}",
            "commit or stash",
        )
    if not state.upstream and not state.unborn:
        return v(
            YOURS,
            True,
            SEV_NO_UPSTREAM,
            f"branch {state.branch} was never pushed",
            "git push -u origin HEAD",
        )
    return v(ownership, False, detail="clean and pushed")


# ------------------------------------------------------------------------------------------
# discovery
# ------------------------------------------------------------------------------------------
def discover_repos(roots, cfg: Config, max_depth: int | None = None, deadline=None):
    """Return [(repo_path, enclosing_repo_path_or_empty)].

    Descends INTO a discovered repo so nested clones are found and can be classified.
    A naive walker that stops at the first .git cannot see them at all, which silently
    turns the nested-repo rule into dead code.
    """
    depth_cap = cfg.max_depth if max_depth is None else max_depth
    out: list[tuple[str, str]] = []

    def walk(d: Path, depth: int, enclosing: str) -> None:
        if depth > depth_cap or (deadline and time.monotonic() > deadline):
            return
        try:
            entries = list(d.iterdir())
        except (OSError, PermissionError):
            return
        here = enclosing
        try:
            if (d / ".git").exists():
                out.append((str(d), enclosing))
                here = str(d)
        except OSError:
            pass
        for e in entries:
            try:
                if not e.is_dir() or e.is_symlink():
                    continue
            except OSError:
                continue
            if e.name in cfg.exclude_dirs:
                continue
            if _matches(str(e), cfg.prune_markers):
                continue
            walk(e, depth + 1, here)

    for r in roots:
        p = Path(r)
        if p.exists():
            walk(p, 0, "")
    seen, uniq = set(), []
    for path, nested in out:
        key = _norm(path)
        if key not in seen:
            seen.add(key)
            uniq.append((path, nested))
    return uniq


def survey(
    roots, cfg: Config, max_depth: int | None = None, deadline=None
) -> list[Verdict]:
    """Read every discovered repo CONCURRENTLY. git spends its time in subprocess wait,
    which releases the GIL, so threads are the right tool and the 8-wide pool turns a
    ~60 s serial scan into a few seconds."""
    found = discover_repos(roots, cfg, max_depth, deadline)
    if not found:
        return []
    nested_by_path = {p: n for p, n in found}
    verdicts: list[Verdict] = []
    try:
        with _fut.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {pool.submit(read_repo_state, p): p for p, _ in found}
            for fut in _fut.as_completed(futures):
                path = futures[fut]
                try:
                    st = fut.result()
                except Exception:  # noqa: BLE001 - one bad repo must not sink the scan
                    continue
                if st is not None:
                    verdicts.append(
                        classify(
                            replace(st, nested_in=nested_by_path.get(path, "")), cfg
                        )
                    )
    except Exception:  # noqa: BLE001 - fall back to serial if the pool cannot start
        for path, nested in found:
            st = read_repo_state(path)
            if st is not None:
                verdicts.append(classify(replace(st, nested_in=nested), cfg))
    return verdicts


# ------------------------------------------------------------------------------------------
# live-tree drift: what sync-from-live.ps1 would carry that the repo does not have yet
# ------------------------------------------------------------------------------------------
def scan_sync_drift(
    pairs, cfg: Config, cap: int | None = None, deadline=None
) -> list[DriftReport]:
    """Compare live trees against their repo counterparts. SIZE, never hash: hashing 18,628
    files costs seconds a Stop hook does not have. Size-differs is sufficient evidence to
    say "go look"; `sync-from-live.ps1 -Drift` is the authoritative comparison and is what
    the message points at. Same-size-but-changed is invisible here, and that is a deliberate
    accepted false-negative, not an oversight.

    Prunes DURING the walk (os.walk + dirnames[:]), not after: the raw skills tree holds
    18,002 files of which only 1,645 survive the exclusions, and filtering rglob output
    after the fact still pays to visit all 18,002 (measured 7.2 s -> well under 1 s).
    """
    limit = cfg.cap if cap is None else cap
    reports: list[DriftReport] = []
    for live, repo, area in pairs:
        live, repo = Path(live), Path(repo)
        if not live.exists():
            continue
        live_only = differing = scanned = 0
        truncated = False
        live_s = str(live)

        for dirpath, dirnames, filenames in os.walk(live_s):
            if scanned >= limit or (deadline and time.monotonic() > deadline):
                truncated = True
                break
            # A directory carrying its own .git is a SEPARATE REPOSITORY that happens to sit
            # inside our tree; sync-from-live.ps1 refuses to copy it (Test-InNestedRepo) and
            # so must we. crypto-ctf/RsaCtfTool is 10 MB / 193 files of exactly this.
            if dirpath != live_s and os.path.exists(os.path.join(dirpath, ".git")):
                dirnames[:] = []
                continue
            dirnames[:] = [
                d
                for d in dirnames
                if d not in cfg.exclude_dirs
                and not _matches(os.path.join(dirpath, d), cfg.prune_markers)
            ]
            for fn in filenames:
                if scanned >= limit:
                    truncated = True
                    break
                if any(fnmatch.fnmatch(fn, pat) for pat in cfg.exclude_patterns):
                    continue
                scanned += 1
                src = os.path.join(dirpath, fn)
                dest = os.path.join(str(repo), os.path.relpath(src, live_s))
                try:
                    if not os.path.exists(dest):
                        live_only += 1
                    elif os.path.getsize(dest) != os.path.getsize(src):
                        differing += 1
                except OSError:
                    continue
        reports.append(
            DriftReport(
                area=area,
                live_only=live_only,
                differing=differing,
                actionable=live_only + differing,
                scanned=scanned,
                truncated=truncated,
            )
        )
    return reports


def scan_loose_files(loose, cfg: Config) -> list[DriftReport]:
    """sync-from-live.ps1 carries INDIVIDUALLY NAMED loose files, not whole directories.

    Mapping ~/.local/bin wholesale onto tools/monitor reported 35 'drifting' files that
    sync would never touch -- a false-positive class this hook invented for itself, caught
    by running it against the real box rather than fixtures. Only the named files count.
    """
    out = []
    for live, repo, area in loose:
        live, repo = Path(live), Path(repo)
        if not live.exists():
            continue
        try:
            if not repo.exists():
                out.append(DriftReport(area, 1, 0, 1, 1, False))
            elif repo.stat().st_size != live.stat().st_size:
                out.append(DriftReport(area, 0, 1, 1, 1, False))
        except OSError:
            continue
    return out


def default_sync_pairs(home: Path, repo_root: Path):
    """The exact live->repo directory map sync-from-live.ps1 carries."""
    return [
        (home / ".claude" / "rules", repo_root / "rules", "rules"),
        (home / ".claude" / "agents", repo_root / "agents", "agents"),
        (home / ".claude" / "commands", repo_root / "commands", "commands"),
        (home / ".claude" / "hooks", repo_root / "hooks", "hooks"),
        (home / ".agents" / "skills", repo_root / ".agents" / "skills", "skills"),
    ]


def default_loose_files(home: Path, repo_root: Path):
    """The exact $LooseFiles list sync-from-live.ps1 carries."""
    return [
        (
            home / ".local" / "bin" / "codexmon.ps1",
            repo_root / "tools" / "monitor" / "codexmon.ps1",
            "local/bin",
        ),
    ]


# ------------------------------------------------------------------------------------------
# docs hygiene: documentation that no longer describes a reality that exists
# ------------------------------------------------------------------------------------------
# `[label](target)` -- the destination only, with an optional "title" dropped. Targets holding
# a paren are skipped by the character class rather than balanced, which loses a handful of
# exotic URLs (all of which are schemed, so already out of scope) and gains a regex that
# cannot catastrophically backtrack inside a Stop hook.
_MD_LINK = re.compile(r"\[[^\]\n]*\]\(\s*([^()\s]+?)(?:\s+[\"'][^\"'\n]*[\"'])?\s*\)")

# A destination that is not a repo-relative path: URL scheme (incl. a C: drive letter),
# protocol-relative, pure anchor, or site-absolute.
_NOT_A_REL_PATH = re.compile(r"^(?:[A-Za-z][A-Za-z0-9+.\-]*:|//|#|/)")
# Templating / globbing that means "fill this in", not "this file exists".
_TEMPLATED = frozenset('{}<>$*?|"`')


def _tracked_files(repo_root) -> frozenset:
    """The working checkout's tracked paths, forward-slashed, as a set for O(1) membership.

    `git ls-files` is authoritative about what the CHECKED-OUT tree holds -- exactly the
    universe the docs scan reasons over (it reads those same files from disk). A doc pointing
    at a tracked path is fine; a doc pointing at anything else is the candidate. Empty set on
    any failure = the docs scan stands down (see the caller), never a false report.
    """
    out = _git(repo_root, "ls-files", "-z")
    if not out:
        return frozenset()
    return frozenset(p.replace("\\", "/") for p in out.split("\0") if p)


def _tracked_files_ref(repo_root, ref: str) -> frozenset:
    """Paths tracked at a COMMITTED ref (default origin/main), for the coverage check.

    Coverage asks "is this skill/server published to the canonical repo" -- a question the
    working checkout cannot answer, because a sibling agent may have it parked on an unrelated
    feature branch (measured: a checkout sitting on feat/cv-studio-skill made 21 long-committed
    skills read as 'missing'). origin/main is the stable truth and gives the intended
    regression semantics: a skill landing via a PR flips from flagged to silent when it merges.
    Empty on any failure -> the caller falls back to the working-tree set.
    """
    out = _git(repo_root, "ls-tree", "-r", "-z", "--name-only", ref)
    if not out:
        return frozenset()
    return frozenset(p.replace("\\", "/") for p in out.split("\0") if p)


def _load_discriminator():
    """hooks/_shared/use_vs_mention.py, imported lazily and best-effort.

    Returns (Context, find_real) or (None, None). Never raises: a missing shared module
    must not break Stop.
    """
    try:
        shared = str(THIS.parent / "_shared")
        if shared not in sys.path:
            sys.path.insert(0, shared)
        from use_vs_mention import Context, find_real  # noqa: PLC0415

        return Context, find_real
    except Exception:  # noqa: BLE001 - no discriminator -> the link scan stands down
        return None, None


def _link_target_to_relpath(doc_rel: str, target: str) -> str | None:
    """Resolve a link destination to a repo-relative path, or None if it is not one.

    None means "cannot judge" and is the SAFE answer: every rejection here is a
    deliberate false-negative bought to keep the false-positive rate at zero.
    """
    t = (target or "").strip()
    if not t or _NOT_A_REL_PATH.match(t):
        return None
    t = t.split("#", 1)[0].strip()  # drop an intra-document anchor
    if not t:
        return None  # the link was a pure anchor after all
    try:
        t = unquote(t)
    except Exception:  # noqa: BLE001 - a malformed escape is not a broken link
        return None
    if any(c in _TEMPLATED for c in t):
        return None  # `[x]({{cookiecutter.name}}.md)` is a template, not a claim
    base = posixpath.dirname(doc_rel.replace("\\", "/"))
    # normpath collapses "docs/./x" and "docs/../x"; it never emits a leading "./", so no
    # lstrip is needed (an earlier lstrip("./") greedily ate a leading "../", turning an
    # out-of-repo escape into a bare filename and defeating the "startswith(..)" guard).
    resolved = posixpath.normpath(posixpath.join(base, t))
    if resolved in (".", "") or resolved.startswith("..") or posixpath.isabs(resolved):
        return (
            None  # a bare dir ref, or a path that escapes the repo root: out of scope
        )
    return resolved


def scan_docs_hygiene(repo_root, tracked, cfg: Config, deadline=None) -> DocsReport:
    """Two CHEAP, STRUCTURAL signals of documentation rot.

    (1) BROKEN RELATIVE LINKS. A markdown link is the author ASSERTING that a sibling file
        exists; when it does not, the doc is stale by construction. Chosen over the more
        obvious "doc mentions a path that is gone" because a bare `router.py` in a sentence
        is indistinguishable from a concept reference -- that is precisely the use-vs-mention
        defect class this box has already been bitten by three times. The link form carries a
        SYNTACTIC guarantee of intent, so the same signal survives without the guesswork.

        Every match is still put through the shared discriminator with kind="doclink", because
        a doc that TEACHES markdown necessarily contains example links to nowhere. If that
        module cannot be imported the link half STANDS DOWN entirely (judged=False) rather
        than reporting unjudged hits: an advisory hook that cries wolf gets disabled, which
        the module docstring already argues is strictly worse than no hook.

    (2) COMMITTED CRUFT. `*.bak-20260713`, `*.orig`, `*-OLD.md` that made it INTO the repo.
        Pure filename classification over the tracked set: no file is opened, so there is no
        prose to misread and the use-vs-mention risk is structurally zero.

    DELIBERATELY REJECTED, and why:
      - "orphaned dated scratch dir with no inbound link" -- needs a whole-repo inbound-link
        graph, and "unlinked" does not imply "deletable"; this workspace keeps dated audit
        directories on purpose, so it would fire on almost all of them.
      - "index lists an entry that is gone" -- the linked form is already covered by (1); the
        bare-filename-in-a-table form is the same unguessable prose problem as above.

    Cost: ONE `git ls-files` spawn (already paid by the caller) plus a read of each tracked
    doc. Measured 590-742 ms for 3,103 docs / 17.6 MB on this repo.
    """
    Context, find_real = _load_discriminator()
    judged = Context is not None

    docs, cruft = [], []
    for rel in tracked:
        low = rel.lower()
        if any(fnmatch.fnmatch(low, p.lower()) for p in cfg.doc_cruft_patterns):
            cruft.append(rel)
        elif low.endswith(cfg.doc_exts):
            if any(fnmatch.fnmatch(low, p.lower()) for p in cfg.doc_skip_globs):
                continue
            docs.append(rel)
    docs.sort()  # deterministic truncation and deterministic examples

    # Directory prefixes of tracked files, so `[guides](../guides/)` resolves without a stat.
    dirs = set()
    for rel in tracked:
        d = posixpath.dirname(rel)
        while d:
            dirs.add(d)
            d = posixpath.dirname(d)

    broken, scanned, truncated = [], 0, False
    if judged:
        root = str(repo_root)
        for rel in docs:
            if scanned >= cfg.docs_cap or (deadline and time.monotonic() > deadline):
                truncated = True
                break
            try:
                with open(
                    os.path.join(root, rel), encoding="utf-8", errors="replace"
                ) as fh:
                    text = fh.read()
            except OSError:
                continue  # sparse checkout / permissions: absent is not broken
            scanned += 1
            if "](" not in text:
                continue  # fast reject: the vast majority of docs never reach the regex
            ctx = Context(tool_name="", file_path=rel, source="file")
            for m in find_real(text, _MD_LINK, ctx, kind="doclink"):
                target = _link_target_to_relpath(rel, m.group(1))
                if target is None or target in tracked or target in dirs:
                    continue
                if os.path.exists(os.path.join(root, target)):
                    continue  # untracked but real (generated or ignored output)
                broken.append(f"{rel} -> {m.group(1)}")

    return DocsReport(
        broken_links=len(broken),
        cruft_files=len(cruft),
        scanned=scanned,
        truncated=truncated,
        link_examples=tuple(broken[:3]),
        cruft_examples=tuple(sorted(cruft)[:3]),
        judged=judged,
    )


# ------------------------------------------------------------------------------------------
# coverage: a deployed skill / MCP server that never reached version control
# ------------------------------------------------------------------------------------------
def _top_level_dirs(path: Path) -> set:
    """Names of immediate sub-directories of `path` (each is one skill). '' on any failure."""
    try:
        return {
            e.name
            for e in os.scandir(path)
            if e.is_dir() and not e.name.startswith(".")
        }
    except OSError:
        return set()


def _repo_tree_names(tracked, tree: str) -> set:
    """First path segment under `tree/` for every tracked file -- the covered skill names."""
    prefix = tree.replace("\\", "/").rstrip("/") + "/"
    plen = len(prefix)
    names = set()
    for p in tracked:
        if p.startswith(prefix):
            seg = p[plen:].split("/", 1)[0]
            if seg:
                names.add(seg)
    return names


def scan_skills_coverage(home: Path, tracked, cfg: Config) -> CoverageReport:
    """A live skill that is absent from EVERY repo skill tree = deployed-but-uncommitted.

    Directory-and-name granularity, dual-tree by design: the drift half compares FILES within
    ONE mapped pair, so a skill that exists in a DIFFERENT repo tree than the one being walked
    reads as "missing" there. That is the exact shape of this box's blind spot -- ~/.claude/
    skills was never mapped at all. This check unions the live roots, unions the repo trees,
    and flags only names in neither -- so a skill committed to any tree is silent and is never
    double-counted.

    STANDS DOWN if the tracked set is empty: with no coverage data every live skill would look
    missing, and a flood of false names is exactly what gets an advisory hook disabled.
    """
    if not tracked:
        return CoverageReport(area="skills", stood_down=True)
    live = set()
    for root in cfg.live_skill_roots:
        live |= _top_level_dirs(home / root)
    if not live:
        return CoverageReport(area="skills")
    covered = set()
    for tree in cfg.repo_skill_trees:
        covered |= _repo_tree_names(tracked, tree)
    missing = sorted(live - covered)
    return CoverageReport(
        area="skills",
        missing=len(missing),
        names=tuple(missing[: cfg.coverage_name_cap]),
        total_names=len(missing),
    )


def _mcp_repo_relpath(tokens, repo_norm: str):
    """The repo-relative path a server's command/args point at, or None.

    Only servers whose executable lives INSIDE the toolchain repo are in scope: a server run
    from ~/.local/opt or a pip entry-point is deployed independently of this repo and its
    absence from the repo is not drift.
    """
    for t in tokens:
        tn = str(t or "").replace("\\", "/")
        low = tn.lower()
        idx = low.find(repo_norm)
        if idx >= 0:
            rel = tn[idx + len(repo_norm) :].lstrip("/")
            if rel:
                return rel
    return None


def scan_mcp_coverage(
    home: Path, repo_root: Path, tracked, cfg: Config
) -> CoverageReport:
    """An MCP server registered in ~/.mcp.json whose in-repo launcher is NOT tracked.

    The measured hole: the string 'mcp' appeared once in the whole hook, so a server could be
    wired into the live runtime while its `tools/mcp/<name>/` implementation never landed in
    the repo. This reads the manifest, keeps only servers whose command/args resolve to a path
    UNDER the repo, and flags any whose path is untracked and absent. Best-effort throughout:
    a missing or unparseable manifest reports nothing rather than guessing.
    """
    if not tracked:
        return CoverageReport(area="mcp", stood_down=True)
    manifest = home / cfg.mcp_manifest
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return CoverageReport(area="mcp", stood_down=True)
    servers = data.get("mcpServers", data) if isinstance(data, dict) else {}
    if not isinstance(servers, dict):
        return CoverageReport(area="mcp")
    repo_norm = str(repo_root).replace("\\", "/").rstrip("/").lower()
    missing = []
    for name, srv in servers.items():
        if not isinstance(srv, dict):
            continue
        tokens = []
        if srv.get("command"):
            tokens.append(srv["command"])
        tokens += srv.get("args") or []
        if srv.get("cwd"):
            tokens.append(srv["cwd"])
        rel = _mcp_repo_relpath(tokens, repo_norm)
        if rel is None:
            continue  # not a repo-hosted server: out of scope
        rel = posixpath.normpath(rel)
        covered = (
            rel in tracked
            or any(p.startswith(rel + "/") for p in tracked)
            or os.path.exists(os.path.join(str(repo_root), rel))
        )
        if not covered:
            missing.append(str(name))
    missing.sort()
    return CoverageReport(
        area="mcp",
        missing=len(missing),
        names=tuple(missing[: cfg.coverage_name_cap]),
        total_names=len(missing),
    )


# ------------------------------------------------------------------------------------------
# message
# ------------------------------------------------------------------------------------------
def _coverage_lines(covs) -> list[str]:
    """The skills/MCP coverage section -- NAME-bearing, so a missing skill or server cannot
    be skated past as a bare count. [] when nothing is missing."""
    label = {
        "skills": "skill(s) deployed live but absent from every repo skills tree",
        "mcp": "MCP server(s) registered in ~/.mcp.json but not tracked in the repo",
    }
    lines = []
    for c in covs or []:
        if not c or c.actionable == 0:
            continue
        shown = ", ".join(c.names)
        more = (
            f" (+{c.total_names - len(c.names)} more)"
            if c.total_names > len(c.names)
            else ""
        )
        lines.append(
            f"GIT-HYGIENE / {c.area}: {c.missing} {label.get(c.area, c.area)}:"
        )
        lines.append(
            f"  {shown}{more}   ->  add it to the repo (it exists nowhere else)"
        )
    return lines


def _docs_lines(docs) -> list[str]:
    """The docs-hygiene section, or [] when there is nothing actionable to say."""
    if docs is None or docs.actionable == 0:
        return []
    lines = []
    partial = " (a FLOOR: the scan cap/budget expired)" if docs.truncated else ""
    bits = []
    if docs.broken_links:
        bits.append(f"{docs.broken_links} doc link(s) point at a file that is gone")
    if docs.cruft_files:
        bits.append(f"{docs.cruft_files} committed backup/leftover file(s)")
    lines.append(f"GIT-HYGIENE / docs: {'; '.join(bits)}{partial}.")
    for ex in docs.link_examples:
        lines.append(f"  broken link: {ex}")
    for ex in docs.cruft_examples:
        lines.append(f"  stale file:  {ex}   ->  git rm it if it is truly dead")
    return lines


def build_message(verdicts, drifts, docs=None, covs=None) -> str | None:
    reportable = sorted(
        [v for v in verdicts if v.report], key=lambda v: (v.severity, -len(v.detail))
    )
    drifts = [d for d in (drifts or []) if d.actionable > 0]
    cov_lines = _coverage_lines(covs)
    docs_lines = _docs_lines(docs)
    if not reportable and not drifts and not cov_lines and not docs_lines:
        return None

    # Coverage FIRST: a whole missing skill/MCP is the highest-stakes drift and is
    # name-bearing, so it must survive the MAX_LINES cap rather than be dropped after rows.
    lines = list(cov_lines)
    if drifts:
        total = sum(d.actionable for d in drifts)
        partial = (
            " (a FLOOR: the scan budget expired)"
            if any(d.truncated for d in drifts)
            else ""
        )
        areas = ", ".join(f"{d.area} {d.actionable}" for d in drifts[:5])
        lines.append(
            f"GIT-HYGIENE / harness: {total} live file(s){partial} under the synced trees "
            f"are absent from or differ from the toolchain repo [{areas}]."
        )
        lines.append(
            "  -> pwsh -File scripts/sync-from-live.ps1 -Drift   "
            "(then -WhatIf, then commit)"
        )

    if reportable:
        # Same reasoning as coverage-first, applied to the one section that GROWS: the repo
        # half is assembled ABOVE the docs names and the advisory footer, so it must fit the
        # budget those leave rather than consume the cap and let lines[:MAX_LINES] amputate
        # them. Measured pre-fix on 2a748d9 -- 50 repos + both coverage areas + a full docs
        # report emitted exactly 20 lines, and the 4 that fell off the bottom were the 3
        # name-bearing `stale file:` lines and the "Advisory only" footer. Reserving here
        # costs nothing in the common case (no coverage/docs -> the full MAX_ROWS survives)
        # and degrades to 4 rows in the crowded worst case instead of deleting a dimension.
        # -1 = the advisory footer; -2 = this section's own header + its "N more" line.
        room = MAX_LINES - len(lines) - len(docs_lines) - 1 - 2
        rows = max(MIN_ROWS, min(MAX_ROWS, room))
        lines.append(
            f"GIT-HYGIENE / repos: {len(reportable)} of your repo(s) hold work that is not "
            f"safely in version control (vendored + agent-scratch clones already excluded):"
        )
        for v in reportable[:rows]:
            lines.append(f"  [{v.ownership}] {v.name}: {v.detail}  ->  {v.action}")
        if len(reportable) > rows:
            lines.append(
                f"  ... and {len(reportable) - rows} more "
                f"(pwsh -File scripts/repo-sweep.ps1 for the full survey)"
            )
    lines.extend(docs_lines)
    lines.append(
        "  Advisory only -- nothing is blocked. Ignore freely if this is deliberate."
    )
    return "\n".join(lines[:MAX_LINES])


# ------------------------------------------------------------------------------------------
# hook entry point
# ------------------------------------------------------------------------------------------
def _default_roots(home: Path):
    return [home / "source", home / "Documents" / "GitHub", home / "Documents"]


def main() -> int:
    try:
        if (THIS / ".disabled").exists() or os.environ.get(
            "GIT_HYGIENE", ""
        ).lower() in ("off", "0", "false"):
            return 0
        try:
            json.loads(sys.stdin.read() or "{}")
        except Exception:  # noqa: BLE001 - malformed payload must never break Stop
            return 0

        # Frequency throttle. The full survey costs ~5 s and a Stop hook fires at every
        # turn-end, so run it at most once per GIT_HYGIENE_THROTTLE_SEC (default 900 s /
        # 15 min). Ignored drift re-surfaces on the next tick rather than taxing every turn;
        # set the env to 0 to disable. mtime of a stamp file is the clock.
        stamp = THIS / ".last-run"
        try:
            throttle = float(os.environ.get("GIT_HYGIENE_THROTTLE_SEC") or 900)
        except ValueError:
            throttle = 900.0
        try:
            if (
                throttle > 0
                and stamp.exists()
                and (time.time() - stamp.stat().st_mtime) < throttle
            ):
                return 0
        except OSError:
            pass

        home = Path(os.environ.get("USERPROFILE") or os.path.expanduser("~"))
        cfg = replace(
            Config(), owner=os.environ.get("GIT_HYGIENE_OWNER") or Config().owner
        )
        try:
            budget = float(os.environ.get("GIT_HYGIENE_BUDGET") or cfg.budget_s)
        except ValueError:
            budget = cfg.budget_s
        deadline = time.monotonic() + budget

        raw = os.environ.get("GIT_HYGIENE_ROOTS")
        if raw is None:
            roots = _default_roots(home)
        else:
            roots = [Path(r) for r in raw.split(os.pathsep) if r.strip()]

        verdicts = survey(roots, cfg, deadline=deadline)

        repo_root = Path(
            os.environ.get("GIT_HYGIENE_REPO")
            or home / "source" / "agent-skills-toolchain"
        )
        repo_exists = repo_root.exists()

        drifts = []
        if repo_exists and os.environ.get("GIT_HYGIENE_SYNC", "").lower() not in (
            "off",
            "0",
            "false",
        ):
            drifts = scan_sync_drift(
                default_sync_pairs(home, repo_root), cfg, deadline=deadline
            )
            drifts += scan_loose_files(default_loose_files(home, repo_root), cfg)

        # Docs + coverage both reason over the repo's tracked set: fetch it ONCE.
        docs = None
        covs = []
        if repo_exists:
            tracked = _tracked_files(repo_root)
            if tracked and os.environ.get("GIT_HYGIENE_DOCS", "").lower() not in (
                "off",
                "0",
                "false",
            ):
                docs = scan_docs_hygiene(repo_root, tracked, cfg, deadline=deadline)
            if tracked and os.environ.get("GIT_HYGIENE_COVERAGE", "").lower() not in (
                "off",
                "0",
                "false",
            ):
                # Coverage measures against the canonical published tree (origin/main by
                # default), NOT the working branch a sibling may have parked here.
                base = os.environ.get("GIT_HYGIENE_BASE") or "origin/main"
                cov_tracked = _tracked_files_ref(repo_root, base) or tracked
                covs = [
                    scan_skills_coverage(home, cov_tracked, cfg),
                    scan_mcp_coverage(home, repo_root, cov_tracked, cfg),
                ]

        msg = build_message(verdicts, drifts, docs, covs)
        # Stamp AFTER a completed scan (drift or clean) so the throttle counts from the
        # last real survey — a clean pass still suppresses re-scans for the throttle window.
        try:
            stamp.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass
        if msg:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "Stop",
                            "additionalContext": msg,
                        }
                    }
                )
            )
        return 0
    except Exception:  # noqa: BLE001 - fail-open: a crashing gate is worse than none
        return 0


if __name__ == "__main__":
    sys.exit(main())

# D17 2026-09-19: only TOP-LEVEL SKILL.md files count as live skills for hygiene
# scanning (vendored marketplace buckets under skills/synced are false positives).
