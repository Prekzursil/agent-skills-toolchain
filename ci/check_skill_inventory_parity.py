#!/usr/bin/env python3
"""Gate the SET of skills the two dual-write roots hold -- the INVENTORY arm.

WHY THIS EXISTS
---------------
D-001 makes ``.agents/skills`` authoritative and ``skills`` its generated
projection.  ``ci/check_skill_dual_write.py`` enforces that rule on CHANGED
paths: it diffs a range, and for every skill path the range touches it requires a
matching counterpart.  That is correct for its stated job -- catching drift a
change introduces -- and it means a skill the range never touches is invisible to
it.  Reading its green as "the two trees agree" is a scope error.

Measured at HEAD (2026-08-14), both halves of that scope error are live::

    python ci/check_skill_dual_write.py --base HEAD --head HEAD --strict-parity
      -> "OK: changed skill paths match their final-tree counterparts."  exit 0

    canonical-only  12  claim-verify-gate, qdx-rush, microsoft-foundry, and the
                        nine codex-* wrappers
    projection-only  3  harness-module-authoring, patent-fto-search,
                        social-corpus-extraction

Fifteen skills exist in exactly one root and the existing gate reports OK.  This
script is the missing arm: it compares the two roots' NAME SETS directly, with no
reference to any diff, so a standing asymmetry cannot hide behind an untouched
range.

TWO SURFACES, BECAUSE ONE OF THEM LIES
--------------------------------------
"The set of skills" has two defensible readings and they DISAGREE on this tree,
so both are measured:

  * DIRECTORY  a ``<root>/<name>/`` holding at least one file.  This is what
    ``check_skill_dual_write._skill_name`` means by a skill, so it is the surface
    that decides whether that gate would ever have had a row to check.
  * MANIFEST   a ``<root>/<name>/SKILL.md``.  This is what a skill LOADER means:
    a directory without one cannot be selected, no matter what else it holds.

Measured: ``skills/microsoft-foundry/`` holds 42 of the canonical copy's 204
files and NO ``SKILL.md``.  On the directory surface it is symmetric; on the
manifest surface it is canonical-only.  A directory-only gate would have reported
this tree as holding 14 asymmetries and called microsoft-foundry fine -- a
suspiciously-clean parity produced by comparing the wrong collection, which is
exactly the failure this arm exists to catch.  A half-projected skill is worse
than an absent one: it LOOKS present.

So a name that is present as a directory in both roots but carries ``SKILL.md``
in only one is its own violation (``partial-projection``) rather than silence.
``crcp-health`` is the control in the other direction: two script files and no
``SKILL.md`` in EITHER root -- symmetric on both surfaces, and correctly quiet.

WHY IT IS A PINNED RATCHET AND NOT A BARE PARITY CHECK
------------------------------------------------------
Those 15 are real, pre-existing, and each is an owner decision rather than an
accident -- ``claim-verify-gate`` is EXECUTED by ``quality.yml`` from the
canonical root and has no projection counterpart on purpose, and which direction
wins for the other 14 is not this gate's call.  A bare parity check would be red
at HEAD and therefore un-adoptable, which is the same trade
``ci/skill-description-exemptions.txt`` already settled for the description
ratchet.  So the known set is PINNED in ``ci/skill-inventory-baseline.txt`` and
the gate fires on:

  * ``unpinned-asymmetry``  a skill directory in exactly one root, not pinned --
    the regression this arm exists to stop.
  * ``partial-projection``  a skill directory in BOTH roots whose ``SKILL.md`` is
    in only one, not pinned.
  * ``direction-mismatch``  a pinned skill that moved to the OTHER root.  The
    name-set is still asymmetric so a set-difference alone would stay quiet, yet
    the authoritative copy has been deleted and the generated one kept.
  * ``stale-baseline``      a pinned skill that is now symmetric.  Shrink-only:
    reconcile a skill and you MUST delete its line in the same change.
  * ``unknown-baseline``    a pinned skill present in NEITHER root.

FAIL-CLOSED SURFACE, AND WHAT IT DOES AND DOES NOT GUARANTEE
------------------------------------------------------------
Exit 2 (never a pass) when: a root is missing, a root walks EMPTY on EITHER
surface, the two roots resolve to the same directory, or the baseline file is
unreadable or malformed.  Both surfaces are floored because they fail
independently: a broken directory walk and a broken ``SKILL.md`` glob each
produce an empty set whose set-difference is empty, i.e. a clean report from a
measurement that never happened.

The count line prints on every run, green or red, because the count IS the
control: a walk that silently collected the wrong collection is caught by an
implausible number, not by a verdict.  There is deliberately no plausibility
floor beyond >= 1 per root per surface.  A walk that breaks and returns a
fraction of a root produces hundreds of ``unpinned-asymmetry`` rows -- it fails
LOUD by construction, so a magic threshold would be a constant to maintain and
would buy nothing.  The one shape that could fail SILENTLY GREEN is both roots
resolving to the same directory, which yields an empty set-difference on both
surfaces; that is why identical roots are a configuration error rather than a
trivially clean run.

``--source git`` reads the committed tree instead of the working tree.  The two
are mechanically independent enumerations (``os`` walk vs ``git ls-tree``) and
``ci/tests/test_skill_inventory_parity.py`` asserts they agree at HEAD; a
disagreement means an untracked or ignored skill directory, which is information
about the checkout rather than about D-001.

NOT WIRED INTO CI YET.  Author + red-proof only: the private-repo Actions minute
allowance is exhausted, so a workflow edit could not be verified and an
unverifiable CI change stays unshipped.  Wiring is one ``run:`` line in
``.github/workflows/skill-dual-write.yml`` plus the matching marker test.

Exit codes:  0 clean | 1 violations | 2 configuration error (fails CLOSED).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

CANONICAL_ROOT = ".agents/skills"
PROJECTION_ROOT = "skills"
DEFAULT_BASELINE = "ci/skill-inventory-baseline.txt"

#: The file that makes a directory a LOADABLE skill rather than a folder of assets.
MANIFEST = "SKILL.md"

KIND_CANONICAL_ONLY = "canonical-only"
KIND_PROJECTION_ONLY = "projection-only"
KIND_MANIFEST_CANONICAL_ONLY = "skill-md-canonical-only"
KIND_MANIFEST_PROJECTION_ONLY = "skill-md-projection-only"
BASELINE_KINDS = frozenset(
    {
        KIND_CANONICAL_ONLY,
        KIND_PROJECTION_ONLY,
        KIND_MANIFEST_CANONICAL_ONLY,
        KIND_MANIFEST_PROJECTION_ONLY,
    }
)

RULE_UNPINNED = "unpinned-asymmetry"
RULE_PARTIAL = "partial-projection"
RULE_DIRECTION = "direction-mismatch"
RULE_STALE = "stale-baseline"
RULE_UNKNOWN = "unknown-baseline"

MARKER = "skill-inventory-parity"

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_CONFIG = 2

#: ``git ls-tree -r`` emits ``<mode> SP <type> SP <oid> TAB <path>``.  Only a blob
#: is a file; a gitlink is a ``commit`` entry and must not be counted as content.
_BLOB = "blob"


class ConfigurationError(ValueError):
    """The surface could not be measured, so no verdict may be issued.

    Kept distinct from a violation on purpose: a gate that cannot read its inputs
    must exit non-zero rather than report a clean surface it never measured.
    """


@dataclass(frozen=True)
class Inventory:
    """One root's two name sets.  ``manifests`` is always a subset of ``dirs``."""

    root: str
    dirs: frozenset[str]
    manifests: frozenset[str]


def _run_git(repo: Path, args: list[str]) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="surrogateescape",
    )
    if proc.returncode != 0:
        raise ConfigurationError(
            f"git {' '.join(args)} failed: {proc.stderr.strip() or 'no stderr'}"
        )
    return proc.stdout


def _has_file(directory: Path) -> bool:
    """True when ``directory`` holds at least one regular file, at any depth.

    A skill DIRECTORY is one containing content.  Requiring a file keeps this
    enumeration equivalent to ``check_skill_dual_write._skill_name`` (which needs
    at least two path components under the root) and keeps the worktree and git
    enumerations comparable -- git cannot represent an empty directory at all, so
    counting one here would manufacture a phantom asymmetry.
    """
    return any(path.is_file() for path in directory.rglob("*"))


def inventory_from_worktree(repo: Path, root: str) -> Inventory:
    base = repo / root
    if not base.is_dir():
        raise ConfigurationError(f"skill root does not exist: {base.as_posix()}")
    dirs: set[str] = set()
    manifests: set[str] = set()
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        has_manifest = (entry / MANIFEST).is_file()
        # Short-circuit: the manifest IS a file, so the recursive walk is only
        # needed for the rare asset-only directory.
        if has_manifest:
            manifests.add(entry.name)
            dirs.add(entry.name)
        elif _has_file(entry):
            dirs.add(entry.name)
    return Inventory(root=root, dirs=frozenset(dirs), manifests=frozenset(manifests))


def inventory_from_git(repo: Path, root: str, rev: str) -> Inventory:
    """Both name sets under ``root`` in the COMMITTED tree at ``rev``.

    NUL-delimited so a path holding a space or a non-ASCII byte is data rather
    than a parse hazard (``git ls-tree`` C-quotes such paths in its default text
    mode, which a naive reader then drops).
    """
    out = _run_git(repo, ["ls-tree", "-r", "-z", rev, "--", root])
    prefix = f"{root}/"
    dirs: set[str] = set()
    manifests: set[str] = set()
    for record in (r for r in out.split("\0") if r):
        meta, separator, path = record.partition("\t")
        if not separator:
            raise ConfigurationError("git returned a tree record without a path")
        fields = meta.split()
        if len(fields) != 3:
            raise ConfigurationError(f"git returned a malformed tree entry: {path!r}")
        if fields[1] != _BLOB or not path.startswith(prefix):
            continue
        head, separator, rest = path[len(prefix) :].partition("/")
        # No separator means a loose file directly under the root
        # (``skills/SKILLS-MANIFEST.md``), which is not a skill.
        if not separator or not head:
            continue
        dirs.add(head)
        if rest == MANIFEST:
            manifests.add(head)
    return Inventory(root=root, dirs=frozenset(dirs), manifests=frozenset(manifests))


def collect(
    repo: Path, canonical_root: str, projection_root: str, source: str, rev: str
) -> tuple[Inventory, Inventory]:
    """Enumerate both roots, refusing every shape that cannot yield a verdict."""
    if (repo / canonical_root).resolve() == (repo / projection_root).resolve():
        raise ConfigurationError(
            f"the two skill roots resolve to the same directory "
            f"({canonical_root!r} and {projection_root!r}); a set-difference "
            "against itself is empty, which would report a clean surface that was "
            "never measured"
        )
    if source == "git":
        canonical = inventory_from_git(repo, canonical_root, rev)
        projection = inventory_from_git(repo, projection_root, rev)
    else:
        canonical = inventory_from_worktree(repo, canonical_root)
        projection = inventory_from_worktree(repo, projection_root)
    for inventory in (canonical, projection):
        for surface, names in (
            ("skill directory", inventory.dirs),
            (MANIFEST, inventory.manifests),
        ):
            if not names:
                raise ConfigurationError(
                    f"walked {inventory.root!r} (source={source}) and found no "
                    f"{surface}; refusing to report a clean surface from an empty "
                    "walk"
                )
    return canonical, projection


def load_baseline(path: Path) -> dict[str, str]:
    """``{skill: kind}`` from the pinned-asymmetry file.

    A missing or malformed file is a CONFIGURATION error, never an empty pin set:
    silently degrading to "no pins" would flip a shrink-only ratchet into a gate
    whose strictness depends on whether its own input could be read.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(
            f"cannot read baseline {path.as_posix()}: {exc}"
        ) from exc
    pinned: dict[str, str] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        entry = line.strip()
        if not entry or entry.startswith("#"):
            continue
        kind, separator, name = entry.partition(":")
        if not separator or kind not in BASELINE_KINDS or not name.strip():
            raise ConfigurationError(
                f"{path.as_posix()}:{lineno}: expected '<kind>:<skill>' with kind "
                f"in {sorted(BASELINE_KINDS)}, got {entry!r}"
            )
        name = name.strip()
        if name in pinned:
            raise ConfigurationError(
                f"{path.as_posix()}:{lineno}: {name!r} is pinned twice"
            )
        pinned[name] = kind
    return pinned


def _actual_kinds(canonical: Inventory, projection: Inventory) -> dict[str, str]:
    """``{skill: kind}`` for every name that is asymmetric on EITHER surface.

    The manifest surface is consulted only for names present as a directory in
    both roots; for a name already asymmetric at the directory level the manifest
    asymmetry is implied and would only duplicate the finding (and its pin).
    """
    actual = {name: KIND_CANONICAL_ONLY for name in canonical.dirs - projection.dirs}
    actual.update(
        {name: KIND_PROJECTION_ONLY for name in projection.dirs - canonical.dirs}
    )
    for name in canonical.dirs & projection.dirs:
        in_canonical = name in canonical.manifests
        in_projection = name in projection.manifests
        if in_canonical and not in_projection:
            actual[name] = KIND_MANIFEST_CANONICAL_ONLY
        elif in_projection and not in_canonical:
            actual[name] = KIND_MANIFEST_PROJECTION_ONLY
    return actual


def evaluate(
    canonical: Inventory, projection: Inventory, pinned: dict[str, str]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Return (violations, summary).  Violations block; the summary always prints."""
    actual = _actual_kinds(canonical, projection)
    manifest_kinds = {KIND_MANIFEST_CANONICAL_ONLY, KIND_MANIFEST_PROJECTION_ONLY}
    canonical_side = {KIND_CANONICAL_ONLY, KIND_MANIFEST_CANONICAL_ONLY}

    violations: list[dict[str, object]] = []
    for name in sorted(actual):
        kind = actual[name]
        partial = kind in manifest_kinds
        present, missing = (
            (CANONICAL_ROOT, PROJECTION_ROOT)
            if kind in canonical_side
            else (PROJECTION_ROOT, CANONICAL_ROOT)
        )
        what = f"{MANIFEST} for the skill" if partial else "the skill directory"
        pin = pinned.get(name)
        if pin is None:
            violations.append(
                {
                    "rule": RULE_PARTIAL if partial else RULE_UNPINNED,
                    "skill": name,
                    "kind": kind,
                    "detail": (
                        f"{what} exists in {present}/ but not in {missing}/, and is "
                        f"not pinned. Either land the missing copy or, if the "
                        f"asymmetry is deliberate, add '{kind}:{name}' to the "
                        f"baseline with the reason."
                    ),
                }
            )
        elif pin != kind:
            violations.append(
                {
                    "rule": RULE_DIRECTION,
                    "skill": name,
                    "kind": kind,
                    "detail": (
                        f"pinned as '{pin}' but is now '{kind}': what is present in "
                        f"{missing}/ changed. Restore it, or re-pin deliberately."
                    ),
                }
            )

    for name in sorted(pinned):
        if name in actual:
            continue
        known = name in canonical.dirs or name in projection.dirs
        violations.append(
            {
                "rule": RULE_STALE if known else RULE_UNKNOWN,
                "skill": name,
                "kind": pinned[name],
                "detail": (
                    "is now symmetric across both roots; delete its line from the "
                    "baseline in the same change (the baseline is shrink-only)."
                    if known
                    else "is pinned but present in NEITHER root; the skill was "
                    "retired, so delete its baseline line."
                ),
            }
        )

    summary: dict[str, object] = {
        "canonical_root": CANONICAL_ROOT,
        "projection_root": PROJECTION_ROOT,
        "canonical_dirs": len(canonical.dirs),
        "projection_dirs": len(projection.dirs),
        "canonical_manifests": len(canonical.manifests),
        "projection_manifests": len(projection.manifests),
        "dirs_in_both": len(canonical.dirs & projection.dirs),
        "asymmetric": {
            kind: sorted(n for n, k in actual.items() if k == kind)
            for kind in sorted(BASELINE_KINDS)
        },
        "pinned": len(pinned),
    }
    return violations, summary


def render(violations: list[dict[str, object]], summary: dict[str, object]) -> str:
    asymmetric: dict[str, list[str]] = summary["asymmetric"]  # type: ignore[assignment]
    lines = [
        f"skill inventory: dirs {summary['canonical_dirs']}/"
        f"{summary['projection_dirs']} ({summary['dirs_in_both']} in both), "
        f"{MANIFEST} {summary['canonical_manifests']}/"
        f"{summary['projection_manifests']}; asymmetric "
        + ", ".join(
            f"{kind}={len(names)}" for kind, names in sorted(asymmetric.items())
        )
        + f"; {summary['pinned']} pinned"
    ]
    if not violations:
        lines.append(f"SUCCESS:{MARKER} no violations")
        return "\n".join(lines)
    for violation in violations:
        lines.append(
            f"FAILED:{MARKER} {violation['rule']} {violation['skill']} "
            f"-- {violation['detail']}"
        )
    lines.append(f"FAILED:{MARKER} violations={len(violations)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D-001 skill INVENTORY parity gate")
    parser.add_argument("--repo", default=".", help="repository root (default: .)")
    parser.add_argument("--canonical-root", default=CANONICAL_ROOT)
    parser.add_argument("--projection-root", default=PROJECTION_ROOT)
    parser.add_argument(
        "--source",
        choices=("worktree", "git"),
        default="worktree",
        help="enumerate the working tree (default) or the committed tree at --rev",
    )
    parser.add_argument("--rev", default="HEAD", help="revision for --source git")
    parser.add_argument(
        "--baseline",
        default=DEFAULT_BASELINE,
        help=f"pinned-asymmetry file (default: {DEFAULT_BASELINE})",
    )
    parser.add_argument(
        "--no-baseline",
        action="store_true",
        help=(
            "measure with NO pins. Strictly stricter than the default -- every "
            "asymmetry fires -- so it can only make this gate redder, never greener."
        ),
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    try:
        canonical, projection = collect(
            repo, args.canonical_root, args.projection_root, args.source, args.rev
        )
        pinned = {} if args.no_baseline else load_baseline(repo / args.baseline)
        violations, summary = evaluate(canonical, projection, pinned)
    except ConfigurationError as exc:
        print(f"FAILED:{MARKER} configuration -- {exc}", file=sys.stderr)
        return EXIT_CONFIG

    summary["source"] = args.source if args.source == "worktree" else f"git:{args.rev}"
    if args.json:
        print(json.dumps({"violations": violations, "summary": summary}, indent=2))
    else:
        print(render(violations, summary))
    return EXIT_VIOLATION if violations else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
