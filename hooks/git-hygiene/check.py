#!/usr/bin/env python
"""Stop hook -- git hygiene: surface work that is NOT safely in version control.

WHAT IT ANSWERS, at session end:
  1. Did I author anything under the LIVE harness trees (~/.claude, ~/.agents, ~/.local/bin)
     that `scripts/sync-from-live.ps1` would carry into the repo but that is not there yet?
     Before that script existed, 462 files / 2.73 MB of harness work were ARCHITECTURALLY
     orphaned -- the repo shipped only repo->live sync, so live-authored work could never
     reach version control at all.
  2. Are any of MY repos holding uncommitted work, unpushed commits, or no upstream?

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
          GIT_HYGIENE_REPO    toolchain repo root for the drift comparison
          GIT_HYGIENE_BUDGET  seconds of wall clock the whole check may spend (default 5)
"""

from __future__ import annotations

import concurrent.futures as _fut
import fnmatch
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

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

MAX_LINES = 16  # a hook nobody reads is a hook nobody keeps
MAX_ROWS = 8
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
    )
    max_depth: int = 2
    # Measured end-to-end on this box: 3.7 s warm, 5.6 s cold. 8 s leaves headroom so a cold
    # cache does not truncate the report; the hook declares truncation when it does happen.
    budget_s: float = 8.0
    cap: int = 40_000


@dataclass(frozen=True)
class RepoState:
    path: str
    origin: str = ""
    has_remote: bool = False
    branch: str = ""  # "" means DETACHED HEAD
    upstream: str = ""
    dirty: int = 0
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


def _parse_status_v2(out: str):
    """Parse `git status --porcelain=v2 --branch`.

    One call yields oid (unborn?), head (detached?), upstream, ahead/behind and every
    dirty entry. Replaces six separate `git` spawns -- the difference between 1,322 ms
    and ~170 ms per repo, measured.
    """
    branch, upstream, ahead, dirty, unborn = "", "", 0, 0, False
    for line in out.splitlines():
        if not line:
            continue
        if line[0] != "#":
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
    return branch, upstream, ahead, dirty, unborn


def read_repo_state(path) -> RepoState | None:
    p = Path(path)
    dot = p / ".git"
    if not dot.exists():
        return None
    branch, upstream, ahead, dirty, unborn = _parse_status_v2(
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

    # Nothing uncommitted and nothing unique here: a detached HEAD or an empty `git init`
    # cannot lose work it does not have. (~/Documents/Misc is exactly the latter.)
    if state.dirty == 0 and (detached or (state.unborn and ownership == NO_REMOTE)):
        return v(ownership, False, detail="nothing at risk")

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
            f"{state.dirty} uncommitted file(s) {where}, and the branch has no upstream",
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
            f"{state.dirty} uncommitted file(s) {where}",
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
# message
# ------------------------------------------------------------------------------------------
def build_message(verdicts, drifts) -> str | None:
    reportable = sorted(
        [v for v in verdicts if v.report], key=lambda v: (v.severity, -len(v.detail))
    )
    drifts = [d for d in (drifts or []) if d.actionable > 0]
    if not reportable and not drifts:
        return None

    lines = []
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
        lines.append(
            f"GIT-HYGIENE / repos: {len(reportable)} of your repo(s) hold work that is not "
            f"safely in version control (vendored + agent-scratch clones already excluded):"
        )
        for v in reportable[:MAX_ROWS]:
            lines.append(f"  [{v.ownership}] {v.name}: {v.detail}  ->  {v.action}")
        if len(reportable) > MAX_ROWS:
            lines.append(
                f"  ... and {len(reportable) - MAX_ROWS} more "
                f"(pwsh -File scripts/repo-sweep.ps1 for the full survey)"
            )
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

        drifts = []
        if os.environ.get("GIT_HYGIENE_SYNC", "").lower() not in ("off", "0", "false"):
            repo_root = Path(
                os.environ.get("GIT_HYGIENE_REPO")
                or home / "source" / "agent-skills-toolchain"
            )
            if repo_root.exists():
                drifts = scan_sync_drift(
                    default_sync_pairs(home, repo_root), cfg, deadline=deadline
                )
                drifts += scan_loose_files(default_loose_files(home, repo_root), cfg)

        msg = build_message(verdicts, drifts)
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
