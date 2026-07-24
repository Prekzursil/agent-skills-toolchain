"""D-001 dual-write guard.

Decision D-001 makes ``repo/.agents/skills`` the AUTHORITATIVE skill root and
``repo/skills`` a generated projection.  ``AGENTS.md`` states the operational
form of that rule:

    "`skills/` remains a temporary compatibility copy during migration; do not
     add new canonical content there unless the same change lands in
     `.agents/skills/`."

The default mode enforces exactly that sentence and nothing more:

    For every skill NAME that a change adds or edits under ``skills/<NAME>/``,
    the same change must also add or edit NON-EMPTY content under
    ``.agents/skills/<NAME>/``.

It is intentionally a DIFF guard, not a tree-parity guard.  A tree-parity check
would fire on the pre-existing backlog (skills that already live in only one
tree) and would therefore be un-adoptable without a mass migration first.  This
guard only asks that a change not make the divergence worse.  CI opts into
``--strict-parity``, which applies D-001's generated-projection rule to changed
paths in EITHER root by comparing their entries in the final tree/index.

False negatives that earlier revisions of this guard carried are closed here,
and each is pinned by a test in ``ci/tests``:

  * ``canonical-deleted`` -- a commit that DELETES ``.agents/skills/foo/SKILL.md``
    while EDITING ``skills/foo/SKILL.md`` used to pass, because the status
    filter was applied only to the projection side.  Its net effect is to CREATE
    a projection-only skill, i.e. the very violation this guard exists to stop.
  * ``canonical-empty`` -- the canonical obligation used to be discharged by ANY
    path under ``.agents/skills/<NAME>/``, including a zero-byte ``.keep``
    placeholder.  The obligation is now content-level: at least one added or
    edited canonical path must have a non-empty post-image blob.
  * C-QUOTED PATHS -- ``git diff --name-status`` C-quotes any path holding a
    non-ASCII byte, and a line parser then failed the ``skills/`` prefix test
    and dropped the skill entirely.  All diff parsing is NUL-delimited (``-z``).
  * POST-IMAGE DESYNCHRONISATION -- resolving post-images by writing one
    ``<rev>:<path>`` per LINE into ``git cat-file --batch-check`` and zipping the
    output back BY INDEX breaks on a path containing a NEWLINE (legal on the
    Linux runner this gate executes on): every later path then reads another
    file's size, and a 0-byte placeholder can borrow a non-empty one.  Post-image
    MODE and OID now come from ``git diff --raw -z`` -- same NUL-delimited record
    as the path -- and only OBJECT IDS are ever fed to ``cat-file``.  No path
    text enters a protocol that echoes its input, which is the structural end of
    this defect class rather than a fix for one spelling of it.
  * ``canonical-not-a-file`` -- a symlink under ``.agents/skills/<NAME>/`` used
    to discharge the obligation, because its blob (the target string) is
    non-empty.  A canonical row now discharges only if its post-image is a
    REGULAR file (mode 100644/100755).

KNOWN RESIDUAL, stated rather than hidden, and NOT claimed to be exhaustive:
the default rule is non-empty-content-level, NOT equivalence-level.  A one-byte
canonical placeholder still discharges the obligation, and two copies that are
both touched but written with DIFFERENT text still pass.  ``--strict-parity``
closes both by comparing every changed skill path with its counterpart in the
FINAL tree (or staged index).  That final-tree comparison also permits a
projection-only repair when it restores parity with unchanged canonical content.
The flag remains opt-in for local callers because it is a strictly larger policy
change; CI opts in after running this script's acceptance suite.  ``--allowlist``
is still an unguarded escape hatch.

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

# Strict generated-projection mode also checks deletions and type changes.  A
# deletion passes only when the counterpart is absent in the final tree too;
# the generator itself never creates deletions.
STRICT_CHANGES = frozenset("ADMT")

# Post-image modes that can carry skill CONTENT.  120000 (symlink) and 160000
# (gitlink) are blobs/commits, not files, and must not discharge an obligation.
REGULAR_MODES = frozenset({"100644", "100755"})
NULL_OID = "0" * 40

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

REASON_MISSING = "canonical-missing"
REASON_DELETED = "canonical-deleted"
REASON_EMPTY = "canonical-empty"
REASON_NONFILE = "canonical-not-a-file"
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
    REASON_NONFILE: (
        "the canonical side of this change is not a regular file (a symlink or "
        "a submodule entry); land the real content under {canon}/{name}/."
    ),
    REASON_DIVERGENT: (
        "the final canonical and generated-projection entries are missing, "
        "non-regular, or differ in mode/blob (--strict-parity)."
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
        errors="surrogateescape",
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


def raw_entries(
    repo: str, base: str | None, head: str, staged: bool
) -> dict[str, tuple[str, str]]:
    """``{path: (post_image_mode, post_image_oid)}`` for the change.

    ``git diff --raw`` carries the post-image MODE and OID in the SAME
    NUL-delimited record as the path, so the correspondence never has to be
    re-established by position in a second, path-fed protocol -- which is how a
    newline in a filename used to shift every later post-image onto the wrong
    file.  ``--no-abbrev`` is REQUIRED: ``git diff --raw`` abbreviates OIDs to
    seven characters by default (measured, git 2.52).
    """
    args = ["diff", "--raw", "-z", "--no-renames", "--no-abbrev"]
    if staged:
        args.insert(1, "--cached")
    else:
        args.append(f"{base}...{head}")
    fields = [f for f in _run_git(repo, args).split("\0") if f != ""]
    entries: dict[str, tuple[str, str]] = {}
    i = 0
    while i + 1 < len(fields):
        # :<srcmode> <dstmode> <srcoid> <dstoid> <status>
        meta = fields[i].lstrip(":").split()
        if len(meta) < 5:
            i += 1
            continue
        status = meta[4][:1]
        # Defensive: --no-renames means R/C cannot appear, but such a record
        # carries TWO paths and the DESTINATION is the second one.
        span = 2 if status in {"R", "C"} else 1
        if i + span >= len(fields):
            break
        if meta[3] != NULL_OID and len(meta[3]) < 40:
            raise GitError(
                f"git returned an ABBREVIATED object id ({meta[3]!r}); "
                "--no-abbrev is required or an ambiguous prefix can be resolved "
                "to the wrong object"
            )
        entries[fields[i + span]] = (meta[1], meta[3])
        i += span + 1
    return entries


def blob_sizes(repo: str, oids: list[str]) -> dict[str, int]:
    """``{oid: size}`` from ONE ``git cat-file --batch-check``.

    stdin is OBJECT IDS ONLY -- forty hex characters, which cannot contain a
    newline, a space or a quote -- so nothing an author can name a file can
    desynchronise this parse.  A record-count mismatch is raised rather than
    zipped over: a detector that silently mis-aligns is worse than none.
    """
    if not oids:
        return {}
    out = _run_git(
        repo, ["cat-file", "--batch-check"], stdin="".join(f"{o}\n" for o in oids)
    )
    lines = out.splitlines()
    if len(lines) != len(oids):
        raise GitError(
            f"cat-file --batch-check returned {len(lines)} records for "
            f"{len(oids)} object ids; refusing to guess the correspondence"
        )
    sizes: dict[str, int] = {}
    for oid, line in zip(oids, lines):
        parts = line.split()
        if len(parts) == 3 and parts[1] == "blob" and parts[2].isdigit():
            sizes[oid] = int(parts[2])
    return sizes


def post_images(
    repo: str, entries: dict[str, tuple[str, str]], paths: list[str]
) -> tuple[dict[str, tuple[str, int] | None], set[str]]:
    """``({path: (oid, size) | None}, {paths whose post-image is not a file})``.

    ``None`` means "nothing here can discharge an obligation": absent from the
    diff, a null OID, a non-regular mode, or an object git will not size.
    """
    result: dict[str, tuple[str, int] | None] = {}
    nonfile: set[str] = set()
    pending: dict[str, str] = {}
    for path in paths:
        entry = entries.get(path)
        if entry is None:
            result[path] = None
            continue
        mode, oid = entry
        if not oid or oid == NULL_OID:
            result[path] = None
        elif mode not in REGULAR_MODES:
            result[path] = None
            nonfile.add(path)
        else:
            pending[path] = oid
    sizes = blob_sizes(repo, sorted(set(pending.values())))
    for path, oid in pending.items():
        size = sizes.get(oid)
        result[path] = None if size is None else (oid, size)
    return result, nonfile


def final_entries(repo: str, head: str, staged: bool) -> dict[str, tuple[str, str]]:
    """Return ``{path: (mode, oid)}`` from the final tree or staged index.

    Strict parity is a property of the RESULT, not of which rows happened to be
    present in one diff.  Reading the final tree lets a projection-only repair
    match canonical content that was committed before the inspected range.
    Both protocols are NUL-delimited, so legal whitespace in a path is data.
    """
    if staged:
        out = _run_git(
            repo,
            ["ls-files", "--stage", "-z", "--", CANONICAL_ROOT, PROJECTION_ROOT],
        )
    else:
        out = _run_git(
            repo,
            ["ls-tree", "-r", "-z", head, "--", CANONICAL_ROOT, PROJECTION_ROOT],
        )

    entries: dict[str, tuple[str, str]] = {}
    for record in (r for r in out.split("\0") if r):
        meta, separator, path = record.partition("\t")
        if not separator:
            raise GitError("git returned a tree record without a path separator")
        fields = meta.split()
        if staged:
            if len(fields) != 3 or fields[2] != "0":
                raise GitError(
                    f"staged index contains an unmerged or malformed entry for {path!r}"
                )
            mode, oid = fields[:2]
        else:
            if len(fields) != 3:
                raise GitError(f"git returned a malformed tree entry for {path!r}")
            mode, obj_type, oid = fields
            if obj_type not in {"blob", "commit"}:
                raise GitError(f"git returned unexpected object type {obj_type!r}")
        entries[path] = (mode, oid)
    return entries


def evaluate(
    rows: list[tuple[str, str]],
    allow: set[str],
    post: dict[str, tuple[str, int] | None],
    nonfile: set[str] | None = None,
) -> dict[str, dict[str, object]]:
    """Return {skill_name: {reason, paths, detail}} for violations."""
    nonfile = nonfile or set()
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
            reason = (
                REASON_NONFILE
                if all(r[2] in nonfile for r in mutating)
                else REASON_EMPTY
            )
            violations[name] = {
                "reason": reason,
                "paths": paths,
                "detail": sorted(r[2] for r in mutating),
            }
    return violations


def evaluate_strict(
    rows: list[tuple[str, str]],
    allow: set[str],
    final: dict[str, tuple[str, str]],
) -> dict[str, dict[str, object]]:
    """Require changed skill paths to be byte- and mode-identical in the final tree.

    The final tree is the load-bearing distinction from default mode: a repair
    may touch only ``skills/`` when its canonical counterpart already existed,
    while a canonical-only edit must still fail until its generated projection
    is committed.  Projection-only files outside the changed path set are legacy
    routing debt and are preserved rather than turned into a whole-tree gate.
    """
    bad: dict[str, list[tuple[str, str]]] = {}
    deleted = {path for status, path in rows if status == "D"}
    for status, path in rows:
        if status not in STRICT_CHANGES:
            continue
        root = PROJECTION_ROOT
        other = CANONICAL_ROOT
        name = _skill_name(path, root)
        if name is None:
            root, other = other, root
            name = _skill_name(path, root)
        if name is None or name in allow:
            continue
        rel = _skill_rel(path, root)
        counterpart = f"{other}/{name}/{rel}"
        left = final.get(path)
        right = final.get(counterpart)
        regular = left is None or left[0] in REGULAR_MODES
        counterpart_regular = right is None or right[0] in REGULAR_MODES
        unpaired_deletion = status == "D" and counterpart not in deleted
        if left != right or not regular or not counterpart_regular or unpaired_deletion:
            bad.setdefault(name, []).append((path, counterpart))

    return {
        name: {
            "reason": REASON_DIVERGENT,
            "paths": sorted(path for path, _counterpart in pairs),
            "detail": sorted(
                f"final counterpart: {counterpart}" for _path, counterpart in pairs
            ),
        }
        for name, pairs in sorted(bad.items())
    }


def _report(
    violations: dict[str, dict[str, object]], *, strict_parity: bool = False
) -> None:
    print("D-001 DUAL-WRITE VIOLATION")
    if strict_parity:
        print(
            f"{CANONICAL_ROOT}/ is authoritative and {PROJECTION_ROOT}/ is its "
            "generated projection. These changed paths do not match in the "
            "final tree:"
        )
    else:
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
        help="require changed paths to have byte-identical final-tree counterparts",
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
        if ns.strict_parity:
            final = final_entries(ns.repo, head, ns.staged)
            post: dict[str, tuple[str, int] | None] = {}
            nonfile: set[str] = set()
        else:
            wanted = [
                p
                for status, p in rows
                if status in MUTATING
                and (
                    _skill_name(p, PROJECTION_ROOT) is not None
                    or _skill_name(p, CANONICAL_ROOT) is not None
                )
            ]
            entries = raw_entries(ns.repo, base, head, ns.staged)
            post, nonfile = post_images(ns.repo, entries, wanted)
    except GitError as exc:
        sys.stderr.write(f"{exc}\n")
        return EXIT_USAGE

    allow = _load_allowlist(ns.allowlist)
    if ns.strict_parity:
        violations = evaluate_strict(rows, allow, final)
    else:
        violations = evaluate(rows, allow, post, nonfile=nonfile)

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
    elif not violations and ns.strict_parity:
        print("OK: changed skill paths match their final-tree counterparts.")
    elif not violations:
        print(
            f"OK: no {PROJECTION_ROOT}/ change lacks a {CANONICAL_ROOT}/ counterpart."
        )
    else:
        _report(violations, strict_parity=ns.strict_parity)

    return EXIT_OK if not violations else EXIT_VIOLATION


if __name__ == "__main__":
    raise SystemExit(main())
