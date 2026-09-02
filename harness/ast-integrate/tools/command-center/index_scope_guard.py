#!/usr/bin/env python3
"""Shared git-index contamination guard (IMP-0428).

Concurrent sessions sharing one working tree must not `git add -A` / `git add .`
/ `git commit -a`. Those forms sweep a sibling agent's files into the index.
This module:

* refuses broad staging forms without mutating the index
* requires a non-empty, non-global declared file scope
* stages only an explicit path list via ``git add -- <paths>``
* verifies ``git diff --cached --name-only`` against that scope before any
  commit is offered
* never auto-corrects (unstages) a contaminated index; the orchestrator sees
  the out-of-scope paths and decides

Scratch-repo helpers (``init_scratch_repo``, ``plant_unit_and_sibling``) exist
so probes can run against an isolated git tree. Mutating git subcommands are
refused if the target looks like this program's worktree.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

UNIT_FILE = "unit/work.txt"
SIBLING_FILE = "sibling/secret.txt"
PROGRAM_CATALOG = Path("command-center") / "WORK-UNIT-CATALOG.json"
MUTATING_GIT = frozenset(
    {
        "add",
        "commit",
        "reset",
        "checkout",
        "switch",
        "restore",
        "stash",
        "rebase",
        "rm",
        "mv",
        "merge",
        "cherry-pick",
        "revert",
        "clean",
        "update-index",
    }
)
BROAD_SCOPE_TOKENS = frozenset({".", "*", "**", "/", "~", ""})
BROAD_ADD_LONG = frozenset({"--all", "--update", "--no-ignore-removal"})
BROAD_ADD_SHORT = frozenset({"A", "u"})
BROAD_COMMIT_LONG = frozenset({"--all"})
BROAD_COMMIT_SHORT = frozenset({"a"})
BROAD_PATHS = frozenset({".", "*", "**"})


class Codes:
    OK = "INDEX_OK"
    BROAD_STAGE = "INDEX_BROAD_STAGE"
    TRAVERSAL = "INDEX_TRAVERSAL"
    EMPTY_SCOPE = "INDEX_EMPTY_SCOPE"
    COMMIT_REFUSED = "INDEX_COMMIT_REFUSED"
    CONTAMINATED = "INDEX_CONTAMINATED"
    PATH_OUT_OF_SCOPE = "INDEX_PATH_OUT_OF_SCOPE"
    PROGRAM_TREE = "INDEX_PROGRAM_TREE"


@dataclass
class ArgvClass:
    broad: bool
    code: str
    flags: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    reason: str = ""
    verb: str = ""

    def to_dict(self) -> dict:
        return {
            "broad": self.broad,
            "code": self.code,
            "flags": list(self.flags),
            "paths": list(self.paths),
            "reason": self.reason,
        }


@dataclass
class GuardResult:
    allowed: bool
    code: str
    command: str = ""
    message: str = ""
    staged: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    in_scope_staged: list[str] = field(default_factory=list)
    requested_paths: list[str] = field(default_factory=list)
    unguarded_broad_would_add: list[str] = field(default_factory=list)
    commit_offered: bool = False
    index_mutated: bool = False
    auto_corrected: bool = False

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "auto_corrected": self.auto_corrected,
            "code": self.code,
            "command": self.command,
            "commit_offered": self.commit_offered,
            "in_scope_staged": list(self.in_scope_staged),
            "index_mutated": self.index_mutated,
            "message": self.message,
            "out_of_scope": list(self.out_of_scope),
            "requested_paths": list(self.requested_paths),
            "staged": list(self.staged),
            "unguarded_broad_would_add": list(self.unguarded_broad_would_add),
        }


def _posix(rel: str) -> str:
    return rel.replace("\\", "/").lstrip("./")


def is_program_worktree(repo: Path) -> bool:
    return (Path(repo) / PROGRAM_CATALOG).is_file()


def git(
    repo: Path,
    *args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run git in *repo*. Mutating verbs are refused on the program worktree."""
    repo = Path(repo)
    verb = args[0] if args else ""
    if is_program_worktree(repo) and verb in MUTATING_GIT:
        raise RuntimeError(
            f"refusing git {verb} on program worktree {repo}; "
            "IMP-0428 mutates scratch repos only"
        )
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} in {repo} failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout or '').strip()}"
        )
    return proc


def init_scratch_repo(path: Path) -> Path:
    """Create an isolated git repo. Never pointed at the program worktree."""
    path = Path(path)
    if is_program_worktree(path):
        raise RuntimeError(f"refusing to re-init program worktree {path}")
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", check=True)
    git(path, "config", "user.email", "imp0428@invalid", check=True)
    git(path, "config", "user.name", "IMP-0428", check=True)
    git(path, "config", "commit.gpgsign", "false", check=True)
    git(path, "config", "core.autocrlf", "false", check=True)
    return path


def plant_unit_and_sibling(repo: Path) -> tuple[str, str]:
    """Plant the catalog's both-states pair: unit file vs sibling secret."""
    repo = Path(repo)
    unit = repo / UNIT_FILE
    sibling = repo / SIBLING_FILE
    unit.parent.mkdir(parents=True, exist_ok=True)
    sibling.parent.mkdir(parents=True, exist_ok=True)
    if not unit.exists():
        unit.write_text("unit work\n", encoding="utf-8")
    if not sibling.exists():
        sibling.write_text("sibling secret\n", encoding="utf-8")
    return UNIT_FILE, SIBLING_FILE


def cached_paths(repo: Path) -> list[str]:
    proc = git(repo, "diff", "--cached", "--name-only", "-z")
    if proc.returncode != 0:
        proc = git(repo, "diff", "--cached", "--name-only")
        names = [
            _posix(line.strip())
            for line in (proc.stdout or "").splitlines()
            if line.strip()
        ]
        return sorted(set(names))
    names = [_posix(p) for p in (proc.stdout or "").split("\0") if p]
    return sorted(set(names))


def unguarded_broad_would_add(repo: Path) -> list[str]:
    """Oracle for the vacuous-control: what raw ``git add -A`` would stage."""
    proc = git(repo, "add", "-A", "--dry-run")
    found: list[str] = []
    for line in (proc.stdout or "").splitlines():
        text = line.strip()
        if text.startswith("add "):
            rest = text[4:].strip().strip("'\"")
            if rest:
                found.append(_posix(rest))
    return sorted(set(found))


def _scope_items(scope: Sequence[str] | Iterable[str]) -> list[str]:
    return [_posix(str(s).strip()) for s in scope]


def scope_is_usable(scope: Sequence[str] | Iterable[str]) -> bool:
    items = [s for s in _scope_items(scope) if s]
    if not items:
        return False
    for grant in items:
        if grant in BROAD_SCOPE_TOKENS or grant.rstrip("/") in BROAD_SCOPE_TOKENS:
            return False
    return True


def in_declared_scope(rel: str, scope: Sequence[str] | Iterable[str]) -> bool:
    rel = _posix(rel)
    if not rel or rel in BROAD_PATHS:
        return False
    for grant in _scope_items(scope):
        if not grant or grant in BROAD_SCOPE_TOKENS:
            continue
        directory = grant.endswith("/")
        base = grant.rstrip("/")
        if rel == base:
            return True
        if rel.startswith(base + "/"):
            return True
        if directory and rel == grant:
            return True
    return False


def rel_inside_repo(repo: Path, raw: str) -> str | None:
    """Return repo-relative posix path, or None if *raw* escapes the repo."""
    root = Path(repo).resolve()
    given = Path(raw)
    if given.is_absolute():
        candidate = Path(os.path.normpath(str(given)))
    else:
        candidate = Path(os.path.normpath(str(root / raw)))
    try:
        rel = candidate.resolve().relative_to(root)
    except ValueError:
        return None
    posix = rel.as_posix()
    if posix.startswith("../") or posix == "..":
        return None
    return posix


def _split_argv(argv: Sequence[str]) -> tuple[str, list[str], list[str]]:
    tokens = [str(t) for t in argv]
    if tokens and tokens[0] == "git":
        tokens = tokens[1:]
    verb = tokens[0] if tokens else ""
    rest = tokens[1:]
    flags: list[str] = []
    paths: list[str] = []
    seen_dd = False
    for tok in rest:
        if seen_dd:
            paths.append(tok)
            continue
        if tok == "--":
            seen_dd = True
            continue
        if tok.startswith("-"):
            flags.append(tok)
            continue
        paths.append(tok)
    return verb, flags, paths


def _short_letters(flag: str) -> str:
    if flag.startswith("-") and not flag.startswith("--"):
        return flag[1:]
    return ""


def classify_stage_argv(argv: Sequence[str]) -> ArgvClass:
    verb, flags, paths = _split_argv(argv)
    if verb == "add":
        broad_flags = []
        for flag in flags:
            if flag in BROAD_ADD_LONG:
                broad_flags.append(flag)
                continue
            letters = _short_letters(flag)
            if any(ch in BROAD_ADD_SHORT for ch in letters):
                broad_flags.append(flag)
        # `_posix` strips leading "./", so "." / "./" / "/" normalise to "";
        # test the raw token and the normalised form so `git add .` is broad.
        path_broad = [
            p for p in paths if p in BROAD_PATHS or _posix(p) in BROAD_SCOPE_TOKENS
        ]
        if broad_flags:
            reason = (
                f"broad add flag {broad_flags} stages the whole tree / all tracked"
            )
            return ArgvClass(
                True, Codes.BROAD_STAGE, flags, paths, reason, verb
            )
        if path_broad or (not paths and not flags):
            reason = "broad add path ('.' / '*' / empty) would sweep sibling files"
            return ArgvClass(
                True, Codes.BROAD_STAGE, flags, paths, reason, verb
            )
        return ArgvClass(False, Codes.OK, flags, paths, "scoped add", verb)
    if verb == "commit":
        hit = []
        for flag in flags:
            if flag in BROAD_COMMIT_LONG:
                hit.append(flag)
                continue
            letters = _short_letters(flag)
            if any(ch in BROAD_COMMIT_SHORT for ch in letters):
                hit.append(flag)
        if hit:
            return ArgvClass(
                True,
                Codes.BROAD_STAGE,
                hit,
                paths,
                "commit flag -a stages tracked files globally",
                verb,
            )
        return ArgvClass(False, Codes.OK, flags, paths, "scoped commit", verb)
    return ArgvClass(False, Codes.OK, flags, paths, f"verb {verb}", verb)


def classify_commit_argv(argv: Sequence[str]) -> ArgvClass:
    return classify_stage_argv(argv)


def _refuse(
    code: str,
    message: str,
    *,
    command: str = "stage",
    requested: Sequence[str] | None = None,
) -> GuardResult:
    return GuardResult(
        allowed=False,
        code=code,
        command=command,
        message=message,
        requested_paths=list(requested or []),
        commit_offered=False,
        index_mutated=False,
        auto_corrected=False,
    )


def inspect_index(
    repo: Path,
    scope: Sequence[str],
    verify_cached: bool = True,
) -> GuardResult:
    """Compare the cached set to *scope*. Never mutates the index.

    ``verify_cached=False`` is the known-broken mutation: it skips the
    cached-versus-scope check and therefore allows a contaminated index.
    Live callers must leave the default True.
    """
    cached = cached_paths(repo)
    oos = [p for p in cached if not in_declared_scope(p, scope)]
    inside = [p for p in cached if in_declared_scope(p, scope)]
    if not verify_cached:
        return GuardResult(
            allowed=True,
            code=Codes.OK,
            command="git diff --cached --name-only",
            message="cached-vs-scope check skipped (mutation)",
            staged=cached,
            out_of_scope=oos,
            in_scope_staged=inside,
            commit_offered=True,
            index_mutated=False,
            auto_corrected=False,
        )
    if not scope_is_usable(scope):
        return _refuse(
            Codes.EMPTY_SCOPE,
            "declared file scope is empty or too broad (fail closed)",
            command="git diff --cached --name-only",
        )
    if oos:
        return GuardResult(
            allowed=False,
            code=Codes.CONTAMINATED,
            command="git diff --cached --name-only",
            message=f"cached set has out-of-scope paths {oos}",
            staged=cached,
            out_of_scope=oos,
            in_scope_staged=inside,
            commit_offered=False,
            index_mutated=False,
            auto_corrected=False,
        )
    return GuardResult(
        allowed=True,
        code=Codes.OK,
        command="git diff --cached --name-only",
        message="cached set is within declared scope",
        staged=cached,
        out_of_scope=[],
        in_scope_staged=inside,
        commit_offered=True,
        index_mutated=False,
        auto_corrected=False,
    )


def offer_commit(repo: Path, scope: Sequence[str]) -> GuardResult:
    """Offer a commit only when the cached set is within *scope*.

    A contaminated index is reported and left as-is (no reset / unstage).
    """
    inspected = inspect_index(repo, scope, verify_cached=True)
    inspected.command = "git diff --cached --name-only"
    if inspected.out_of_scope or not inspected.allowed:
        inspected.allowed = False
        inspected.commit_offered = False
        inspected.auto_corrected = False
        inspected.code = Codes.COMMIT_REFUSED
        inspected.message = (
            f"commit not offered: out-of-scope cached paths "
            f"{inspected.out_of_scope}; index left as-is"
        )
        return inspected
    inspected.commit_offered = True
    return inspected


def scoped_stage(
    repo: Path,
    scope: Sequence[str],
    paths: Sequence[str],
    argv: Sequence[str] | None = None,
) -> GuardResult:
    """Stage *paths* if they are in *scope*; refuse broad argv forms.

    Does not unstage out-of-scope files that were already cached.
    """
    repo = Path(repo)
    requested = [str(p) for p in (paths or [])]
    if is_program_worktree(repo):
        return _refuse(
            Codes.PROGRAM_TREE,
            "refusing to stage in the program worktree",
            requested=requested,
        )
    if argv:
        classified = classify_stage_argv(argv)
        if classified.broad:
            return GuardResult(
                allowed=False,
                code=Codes.BROAD_STAGE,
                command=" ".join(str(t) for t in argv),
                message=classified.reason,
                requested_paths=requested or list(classified.paths),
                commit_offered=False,
                index_mutated=False,
                auto_corrected=False,
            )
        if classified.paths and not requested:
            requested = list(classified.paths)
    if not scope_is_usable(scope):
        return _refuse(
            Codes.EMPTY_SCOPE,
            "declared file scope is empty or too broad (fail closed)",
            requested=requested,
        )
    if not requested:
        inspected = inspect_index(repo, scope, verify_cached=True)
        inspected.requested_paths = []
        return inspected

    rels: list[str] = []
    for raw in requested:
        rel = rel_inside_repo(repo, raw)
        if rel is None or rel in BROAD_PATHS:
            return _refuse(
                Codes.TRAVERSAL,
                f"path escapes repo: {raw!r}",
                requested=requested,
            )
        if not in_declared_scope(rel, scope):
            return _refuse(
                Codes.PATH_OUT_OF_SCOPE,
                f"requested path not in declared scope: {rel}",
                requested=requested,
            )
        rels.append(rel)

    before = cached_paths(repo)
    git(repo, "add", "--", *rels, check=True)
    after = cached_paths(repo)
    would = unguarded_broad_would_add(repo)
    oos = [p for p in after if not in_declared_scope(p, scope)]
    inside = [p for p in after if in_declared_scope(p, scope)]
    mutated = after != before
    if oos:
        return GuardResult(
            allowed=False,
            code=Codes.CONTAMINATED,
            command=f"git add -- {' '.join(rels)}",
            message=(
                f"scoped add left out-of-scope cached paths {oos}; "
                "index left as-is (no auto-correct)"
            ),
            staged=after,
            out_of_scope=oos,
            in_scope_staged=inside,
            requested_paths=requested,
            unguarded_broad_would_add=would,
            commit_offered=False,
            index_mutated=mutated,
            auto_corrected=False,
        )
    return GuardResult(
        allowed=True,
        code=Codes.OK,
        command=f"git add -- {' '.join(rels)}",
        message="scoped add; cached set within declared scope",
        staged=after,
        out_of_scope=[],
        in_scope_staged=inside,
        requested_paths=requested,
        unguarded_broad_would_add=would,
        commit_offered=True,
        index_mutated=mutated,
        auto_corrected=False,
    )


def load_declared_scope(
    unit_id: str,
    sidecar: Path | None = None,
    catalog: Path | None = None,
) -> tuple[str, ...]:
    """Load a unit's file scope. Fail closed (empty tuple) if none is declared.

    WORK-UNIT-CATALOG.json has no structured ``declared_file_scope`` field
    today; operational scope is the per-unit sidecar JSON.
    """
    if sidecar is not None and Path(sidecar).is_file():
        data = json.loads(Path(sidecar).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            raw = data.get("paths") or data.get("declared_file_scope") or []
            if isinstance(raw, list):
                return tuple(str(p) for p in raw if str(p).strip())
        return ()
    here = Path(__file__).resolve()
    repo = here.parents[1]
    default = (
        repo
        / "command-center"
        / "p2-wave"
        / "probes"
        / unit_id
        / "declared-scope.json"
    )
    if default.is_file():
        return load_declared_scope(unit_id, sidecar=default)
    if catalog is not None and Path(catalog).is_file():
        doc = json.loads(Path(catalog).read_text(encoding="utf-8"))
        for item in doc.get("work_units") or []:
            if isinstance(item, dict) and item.get("id") == unit_id:
                extra = item.get("declared_file_scope") or item.get("file_scope")
                if isinstance(extra, list):
                    return tuple(str(p) for p in extra if str(p).strip())
                break
    return ()
