#!/usr/bin/env python3
"""D-001 dual-write guard.

Decision D-001 makes ``repo/.agents/skills`` the AUTHORITATIVE skill root and
``repo/skills`` a generated projection.  ``AGENTS.md`` states the operational
form of that rule:

    "`skills/` remains a temporary compatibility copy during migration; do not
     add new canonical content there unless the same change lands in
     `.agents/skills/`."

This script enforces exactly that sentence and nothing more:

    For every skill NAME that a change adds or edits under ``skills/<NAME>/``,
    the same change must also add or edit NON-EMPTY content under
    ``.agents/skills/<NAME>/``.

It is intentionally a DIFF guard, not a tree-parity guard.  A tree-parity check
would fire on the pre-existing backlog (skills that already live in only one
tree) and would therefore be un-adoptable without a mass migration first.  This
guard only asks that a change not make the divergence worse.

Two false negatives that an earlier revision of this guard carried are closed
here, and both are pinned by tests in ``ci/tests``:

  * ``canonical-deleted`` -- a commit that DELETES ``.agents/skills/foo/SKILL.md``
    while EDITING ``skills/foo/SKILL.md`` used to pass, because the status
    filter was applied only to the projection side.  Its net effect is to CREATE
    a projection-only skill, i.e. the very violation this guard exists to stop.
  * ``canonical-empty`` -- the canonical obligation used to be discharged by ANY
    path under ``.agents/skills/<NAME>/``, including a zero-byte ``.keep``
    placeholder.  The obligation is now content-level: at least one added or
    edited canonical path must have a non-empty post-image blob.

KNOWN RESIDUAL, stated rather than hidden: the default rule is
non-empty-content-level, NOT equivalence-level.  A one-byte canonical
placeholder still discharges the obligation, and two copies that are both
touched but written with DIFFERENT text still pass.  ``--strict-parity`` closes
both by requiring a per-relative-path counterpart with an identical blob OID; it
is opt-in because it is a strictly larger policy change (see the adoption cost
measured in the lane report).

Exit codes:
    0  no violation
    1  at least one violation (human report on stdout, ``--json`` for machines)
    2  usage / git error

Usage:
    # PR gate (three-dot: merge-base diff, per rules/common/windows-shell.md #7)
    python ci/check_skill_dual_write.py --base origin/main --head HEAD

    # pre-commit gate
    python ci/check_skill_dual_write.py --staged

    # single commit
    python ci/check_skill_dual_write.py --base <sha>^ --head <sha>
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import PurePosixPath

PROJECTION_ROOT = "skills"
CANONICAL_ROOT = ".agents/skills"

# Statuses that count as "adds or edits".  Renames are decomposed into D+A by
# --no-renames, so R/C never appear.  Applied to BOTH sides: a canonical
# deletion must not discharge a dual-write obligation.
MUTATING = frozenset("AM")

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

REASON_MISSING = "canonical-missing"
REASON_DELETED = "canonical-deleted"
REASON_EMPTY = "canonical-empty"
REASON_DIVERGENT = "canonical-divergent"

_FIX = {
    REASON_MISSING: "also land {canon}/{name}/ in this change.",
    REASON_DELETED: (
        "this change DELETES the canonical copy while editing the projection; "
        "keep (or re-add) {canon}/{name}/ in the same change."
    ),
    REASON_EMPTY: (
        "the canonical side of this change is empty (0 bytes); land the real "
        "content under {canon}/{name}/, not a placeholder."
    ),
    REASON_DIVERGENT: (
        "the canonical copy is missing or differs byte-for-byte from the "
        "projection copy for the paths listed above (--strict-parity)."
    ),
}


class GitError(RuntimeError):
    """git exited non-zero."""


def _run_git(repo: str, args: list[str], stdin: str | None = None) -> str:
    proc = subprocess.run(
        ["git", "-C", repo, *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise GitError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def _diff_rows(
    repo: str, base: str | None, head: str, staged: bool
) -> list[tuple[str, str]]:
    """Return [(status, path)] for the change under inspection.

    NUL-delimited (-z) so a path containing a space, a quote or a non-ASCII
    byte is not C-quoted by git and then mis-parsed here.
    """
    if staged:
        args = ["diff", "--cached", "--name-status", "-z", "--no-renames"]
    else:
        # THREE dots: compare against the merge-base, so an out-of-date branch
        # is not blamed for commits it merely lacks.
        args = ["diff", "--name-status", "-z", "--no-renames", f"{base}...{head}"]
    fields = [f for f in _run_git(repo, args).split("\0") if f != ""]
    rows: list[tuple[str, str]] = []
    i = 0
    while i < len(fields):
        status = fields[i].strip()[:1]
        # Defensive: --no-renames means R/C cannot appear, but if a future
        # caller drops that flag the record carries TWO paths, not one.
        span = 2 if status in {"R", "C"} else 1
        if i + span >= len(fields):
            break
        rows.append((status, fields[i + span]))
        i += span + 1
    return rows


def _skill_name(path: str, root: str) -> str | None:
    """``skills/foo/SKILL.md`` -> ``foo``.  Loose files directly under the root
    (``skills/.gitignore``, ``skills/SKILLS-MANIFEST.md``) are NOT skills."""
    parts = PurePosixPath(path).parts
    root_parts = PurePosixPath(root).parts
    if parts[: len(root_parts)] != root_parts:
        return None
    rest = parts[len(root_parts) :]
    if len(rest) < 2:  # loose file, not a skill directory
        return None
    return rest[0]


def _skill_rel(path: str, root: str) -> str:
    """``skills/foo/scripts/x.py`` -> ``scripts/x.py`` (path inside the skill)."""
    parts = PurePosixPath(path).parts
    root_parts = PurePosixPath(root).parts
    return "/".join(parts[len(root_parts) + 1 :])


def _load_allowlist(path: str | None) -> set[str]:
    if not path:
        return set()
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return set()
    return {
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    }


def post_images(
    repo: str, rev: str | None, paths: list[str]
) -> dict[str, tuple[str, int] | None]:
    """Resolve each path's POST-image blob (oid, size).

    ``rev`` is the head revision for a base...head run, or ``None`` for
    ``--staged`` (post-image is the index entry, spelled ``:<path>``).
    Absent paths map to ``None``.  One ``git cat-file --batch-check`` process
    for the whole set; output is one line per input line, in order, so a path
    containing a space cannot desynchronise the parse.
    """
    if not paths:
        return {}
    prefix = f"{rev}:" if rev is not None else ":"
    stdin = "".join(f"{prefix}{p}\n" for p in paths)
    out = _run_git(repo, ["cat-file", "--batch-check"], stdin=stdin)
    lines = out.splitlines()
    result: dict[str, tuple[str, int] | None] = {}
    for idx, path in enumerate(paths):
        line = lines[idx] if idx < len(lines) else ""
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob" and parts[2].isdigit():
            result[path] = (parts[0], int(parts[2]))
        else:  # "<input> missing" / "<input> ambiguous" / a non-blob entry
            result[path] = None
    return result


def evaluate(
    rows: list[tuple[str, str]],
    allow: set[str],
    post: dict[str, tuple[str, int] | None],
    strict_parity: bool = False,
) -> dict[str, dict[str, object]]:
    """Return {skill_name: {reason, paths, detail}} for violations."""
    projection: dict[str, list[str]] = {}
    canonical: dict[str, list[tuple[str, str, str]]] = {}
    for status, path in rows:
        name = _skill_name(path, PROJECTION_ROOT)
        if name is not None:
            if status in MUTATING:
                projection.setdefault(name, []).append(path)
            continue
        name = _skill_name(path, CANONICAL_ROOT)
        if name is not None:
            rel = _skill_rel(path, CANONICAL_ROOT)
            canonical.setdefault(name, []).append((status, rel, path))

    violations: dict[str, dict[str, object]] = {}
    for name in sorted(projection):
        if name in allow:
            continue
        paths = sorted(projection[name])
        rows_c = canonical.get(name, [])
        mutating = [r for r in rows_c if r[0] in MUTATING]
        substantive = [r for r in mutating if (post.get(r[2]) or ("", 0))[1] > 0]
        if not rows_c:
            violations[name] = {"reason": REASON_MISSING, "paths": paths}
        elif not mutating:
            violations[name] = {
                "reason": REASON_DELETED,
                "paths": paths,
                "detail": sorted(r[2] for r in rows_c),
            }
        elif not substantive:
            violations[name] = {
                "reason": REASON_EMPTY,
                "paths": paths,
                "detail": sorted(r[2] for r in mutating),
            }
        elif strict_parity:
            by_rel = {r[1]: r[2] for r in substantive}
            bad = []
            for ppath in paths:
                rel = _skill_rel(ppath, PROJECTION_ROOT)
                cpath = by_rel.get(rel)
                if cpath is None or post.get(cpath) != post.get(ppath):
                    bad.append(ppath)
            if bad:
                violations[name] = {
                    "reason": REASON_DIVERGENT,
                    "paths": bad,
                    "detail": sorted(by_rel.values()),
                }
    return violations


def _report(violations: dict[str, dict[str, object]]) -> None:
    print("D-001 DUAL-WRITE VIOLATION")
    print(
        f"{CANONICAL_ROOT}/ is the authoritative skill root (AGENTS.md). "
        f"These skills were added/edited under {PROJECTION_ROOT}/ without a "
        f"matching {CANONICAL_ROOT}/ change:"
    )
    for name, info in violations.items():
        reason = str(info["reason"])
        print(f"  - {name}  [{reason}]")
        for p in info["paths"]:
            print(f"      {p}")
        for p in info.get("detail", []):
            print(f"      canonical side: {p}")
        fix = _FIX[reason].format(canon=CANONICAL_ROOT, name=name)
        print(f"      FIX: {fix}")
    print(f"VIOLATIONS: {len(violations)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="D-001 dual-write guard")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", default=None)
    ap.add_argument("--head", default=None)
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--allowlist", default=None)
    ap.add_argument(
        "--strict-parity",
        action="store_true",
        help="also require a byte-identical canonical counterpart per path",
    )
    ap.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)

    if ns.staged and (ns.base is not None or ns.head is not None):
        sys.stderr.write("--staged cannot be combined with --base/--head\n")
        return EXIT_USAGE
    base = ns.base if ns.base is not None else "origin/main"
    head = ns.head if ns.head is not None else "HEAD"

    try:
        rows = _diff_rows(ns.repo, base, head, ns.staged)
        wanted = [
            p
            for status, p in rows
            if status in MUTATING
            and (
                _skill_name(p, PROJECTION_ROOT) is not None
                or _skill_name(p, CANONICAL_ROOT) is not None
            )
        ]
        post = post_images(ns.repo, None if ns.staged else head, wanted)
    except GitError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE

    violations = evaluate(
        rows, _load_allowlist(ns.allowlist), post, strict_parity=ns.strict_parity
    )

    if ns.json:
        print(
            json.dumps(
                {
                    "ok": not violations,
                    "strict_parity": ns.strict_parity,
                    "violations": violations,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif not violations:
        print(
            f"OK: no {PROJECTION_ROOT}/ change lacks a {CANONICAL_ROOT}/ counterpart."
        )
    else:
        _report(violations)

    return EXIT_OK if not violations else EXIT_VIOLATION


if __name__ == "__main__":
    raise SystemExit(main())
