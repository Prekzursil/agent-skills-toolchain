#!/usr/bin/env python3
"""A01 — generate the skill index from the tree, so declarations stop being hand-maintained.

D-001 makes ``repo/.agents/skills`` the authoritative skill root. The published declarations in
``.claude-plugin/marketplace.json`` are currently hand-listed, and hand-lists rot silently: measured
on origin/main 2026-07-23, **110 declared against 336 canonical skills on disk**, with
``"strict": false`` suppressing the signal that would have said so.

This emits the declaration set FROM the tree and can diff it against what is committed. It is the
"single source of truth" half of A01; it deliberately does NOT flip ``strict`` (see below).

RELATIONSHIP TO THE EXISTING GUARD — this does not duplicate it
--------------------------------------------------------------
``ci/check_skill_dual_write.py`` is a DIFF guard: it stops a change from making canonical/projection
divergence WORSE, and is explicitly not a tree-parity check because parity would fire on the
pre-existing backlog and be un-adoptable. This script is the complement: it MEASURES and REGENERATES
that backlog, which is what has to happen before any parity or ``strict`` gate can be turned on.

WHY THIS DOES NOT FLIP ``strict`` TO TRUE
----------------------------------------
Flipping ``strict`` before the backlog is reconciled converts a silent gate into a red one with
150+ findings, which gets the gate disabled rather than the backlog fixed. The sequence that works
is: measure (this script) -> reconcile -> then flip. ``--check`` is therefore advisory by default
and only fails the build under ``--fail-on-drift``, which is opt-in exactly like ``--strict-parity``
in the sibling guard.

WHY THE COUNTER IS NOT ``ls | wc -l``
------------------------------------
``~/.claude/skills`` is a SYMLINK to ``skills.daily/``. ``ls | wc -l`` on it returns **1** — the
link itself — while the tree beneath holds hundreds of skills. A count that disagrees with a
directory walk of the same path is a broken instrument, not a finding. Enumeration here is by
``SKILL.md`` presence under an explicit root, never by listing a directory.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

CANONICAL_ROOT = ".agents/skills"
PROJECTION_ROOTS = ("skills", "skills-claude-only")


def enumerate_skills(repo: pathlib.Path, root: str) -> set[str]:
    """Skill names under `root`, identified by a SKILL.md — never by directory listing."""
    base = repo / root
    if not base.is_dir():
        return set()
    return {p.parent.name for p in base.glob("*/SKILL.md") if p.is_file()}


def declared_from_marketplace(repo: pathlib.Path) -> tuple[set[str], dict]:
    """Return (declared skill names, the parsed marketplace document)."""
    mp = repo / ".claude-plugin" / "marketplace.json"
    if not mp.is_file():
        return set(), {}
    doc = json.loads(mp.read_text(encoding="utf-8"))
    names: set[str] = set()
    for plugin in doc.get("plugins") or []:
        for entry in plugin.get("skills") or []:
            names.add(pathlib.PurePosixPath(str(entry)).name)
    return names, doc


def census(repo: pathlib.Path) -> dict:
    canonical = enumerate_skills(repo, CANONICAL_ROOT)
    projections = {r: enumerate_skills(repo, r) for r in PROJECTION_ROOTS}
    on_disk = set(canonical)
    for names in projections.values():
        on_disk |= names
    declared, _doc = declared_from_marketplace(repo)

    # Control: the enumerator must find a skill we know exists, else every "missing" below is noise.
    control_ok = bool(canonical or any(projections.values()))

    return {
        "control_enumerator_found_skills": control_ok,
        "canonical_root": CANONICAL_ROOT,
        "canonical_count": len(canonical),
        "projection_counts": {r: len(v) for r, v in projections.items()},
        "on_disk_union": len(on_disk),
        "declared_count": len(declared),
        "dangling_declared_but_absent": sorted(declared - on_disk),
        "undeclared_on_disk": sorted(on_disk - declared),
        "canonical_not_declared": sorted(canonical - declared),
        "declared": sorted(declared),
        "canonical": sorted(canonical),
    }


def generate_declarations(repo: pathlib.Path) -> list[str]:
    """The declaration list the tree implies: canonical root first, then projection-only skills.

    Projection-only skills are still declared — dropping them would REMOVE a published skill, and
    D-001 forbids implicit removals. Reconciling them into the canonical root is a separate,
    deliberate migration.
    """
    canonical = enumerate_skills(repo, CANONICAL_ROOT)
    out = [f"./{CANONICAL_ROOT}/{n}" for n in sorted(canonical)]
    for root in PROJECTION_ROOTS:
        only = enumerate_skills(repo, root) - canonical
        out += [f"./{root}/{n}" for n in sorted(only)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument(
        "--check",
        action="store_true",
        help="report drift between tree and declarations",
    )
    ap.add_argument(
        "--emit",
        action="store_true",
        help="print the generated declaration list as JSON",
    )
    ap.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit non-zero when drift exists (opt-in; see module docstring)",
    )
    a = ap.parse_args()

    repo = a.repo.resolve()
    c = census(repo)

    if not c["control_enumerator_found_skills"]:
        print(
            "FAILED: enumerator found no skills at all — wrong --repo, or a broken walk. "
            "Refusing to report drift from an unvalidated detector.",
            file=sys.stderr,
        )
        return 2

    if a.emit:
        print(json.dumps(generate_declarations(repo), indent=2))
        return 0

    print(f"  canonical ({CANONICAL_ROOT}): {c['canonical_count']}")
    for r, n in c["projection_counts"].items():
        print(f"  projection ({r}): {n}")
    print(f"  on-disk union            : {c['on_disk_union']}")
    print(f"  declared in marketplace  : {c['declared_count']}")
    print(
        f"  dangling (declared, absent): {len(c['dangling_declared_but_absent'])} "
        f"{c['dangling_declared_but_absent'][:6]}"
    )
    print(f"  undeclared (on disk)     : {len(c['undeclared_on_disk'])}")
    print(f"  canonical NOT declared   : {len(c['canonical_not_declared'])}")

    drift = bool(c["dangling_declared_but_absent"] or c["undeclared_on_disk"])
    if a.check:
        print(f"  DRIFT: {'yes' if drift else 'no'}")
    return 1 if (drift and a.fail_on_drift) else 0


if __name__ == "__main__":
    raise SystemExit(main())
