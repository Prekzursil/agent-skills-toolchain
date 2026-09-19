#!/usr/bin/env python3
"""A01 — generate the skill index from the tree, so declarations stop being hand-maintained.

D-001 makes ``repo/.agents/skills`` the authoritative skill root. The published declarations in
``.claude-plugin/marketplace.json`` are hand-listed, so omissions and wrong-root entries can remain
silent. This script emits or writes the canonical-first declaration set and checks the committed
index against it by exact route, not just by skill basename.

RELATIONSHIP TO THE EXISTING GUARD — this does not duplicate it
--------------------------------------------------------------
``ci/check_skill_dual_write.py`` is a DIFF guard: it stops a change from making canonical/projection
divergence WORSE, and is explicitly not a tree-parity check because parity would fire on the
pre-existing backlog and be un-adoptable. This script is the complement: it MEASURES and REGENERATES
that backlog, which is what has to happen before parity or ``strict`` policy can be reconsidered.

WHY THIS DOES NOT FLIP ``strict`` TO TRUE
----------------------------------------
The marketplace entry intentionally owns its explicit component list. A strict-mode change also
changes how ``plugin.json`` and conventional ``skills/`` discovery participate, which is separate
from generating this index and could re-adopt the compatibility projection. The explicit
``--check --fail-on-drift`` CI call is the A01 enforcement signal.

WHY DECLARED-ONLY PATHS SURVIVE GENERATION
------------------------------------------
D-001 requires union-before-overwrite and zero implicit removals. Canonical routes win by name,
then projection-only routes are added, then any previously published name absent from every tree is
carried forward at its old route. Removing or replacing such a compatibility name therefore
requires an explicit marketplace edit or an on-disk redirect; ``--write`` never prunes it silently.

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
import io

CANONICAL_ROOT = ".agents/skills"
PROJECTION_ROOTS = ("skills",)
KNOWN_PRESENT_SKILL = "010-editor"
MARKETPLACE_PATH = pathlib.PurePosixPath(".claude-plugin/marketplace.json")


def enumerate_skills(repo: pathlib.Path, root: str) -> set[str]:
    """Skill names under `root`, identified by a SKILL.md — never by directory listing."""
    base = repo / root
    if not base.is_dir():
        return set()
    return {p.parent.name for p in base.glob("*/SKILL.md") if p.is_file()}


def declared_from_marketplace(repo: pathlib.Path) -> tuple[set[str], dict]:
    """Return (declared skill names, the parsed marketplace document)."""
    mp = repo / MARKETPLACE_PATH
    if not mp.is_file():
        return set(), {}
    doc = json.loads(mp.read_text(encoding="utf-8"))
    names: set[str] = set()
    for plugin in doc.get("plugins") or []:
        for entry in plugin.get("skills") or []:
            names.add(pathlib.PurePosixPath(str(entry)).name)
    return names, doc


def marketplace_plugin(doc: dict) -> dict:
    """Return the plugin whose name matches the marketplace name."""
    marketplace_name = doc.get("name")
    plugins = doc.get("plugins")
    if not isinstance(plugins, list):
        raise ValueError("marketplace plugins must be a list")
    matches = [
        plugin
        for plugin in plugins
        if isinstance(plugin, dict) and plugin.get("name") == marketplace_name
    ]
    if len(matches) != 1:
        raise ValueError(
            "marketplace must contain exactly one plugin matching its own name"
        )
    return matches[0]


def marketplace_entries(repo: pathlib.Path) -> list[str]:
    """Return the exact ordered skill routes currently published."""
    mp = repo / MARKETPLACE_PATH
    if not mp.is_file():
        return []
    doc = json.loads(mp.read_text(encoding="utf-8"))
    entries = marketplace_plugin(doc).get("skills")
    if not isinstance(entries, list) or not all(
        isinstance(entry, str) for entry in entries
    ):
        raise ValueError("marketplace plugin skills must be a list of strings")
    return entries


def census(repo: pathlib.Path) -> dict:
    canonical = enumerate_skills(repo, CANONICAL_ROOT)
    projections = {r: enumerate_skills(repo, r) for r in PROJECTION_ROOTS}
    on_disk = set(canonical)
    for names in projections.values():
        on_disk |= names
    declared, _doc = declared_from_marketplace(repo)

    # Control: a nonempty result is not enough; validate one independently known path and its row.
    control_path = repo / CANONICAL_ROOT / KNOWN_PRESENT_SKILL / "SKILL.md"
    control_ok = control_path.is_file() and KNOWN_PRESENT_SKILL in canonical

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
    """Canonical-first union, followed by carried-forward declared-only routes.

    A name is emitted once. The authoritative root wins, then projection roots win in configured
    order. A previously declared name absent from every root is retained unchanged, because D-001
    forbids implicit removals.
    """
    canonical = enumerate_skills(repo, CANONICAL_ROOT)
    out = [f"./{CANONICAL_ROOT}/{n}" for n in sorted(canonical)]
    seen = set(canonical)
    for root in PROJECTION_ROOTS:
        only = enumerate_skills(repo, root) - seen
        out += [f"./{root}/{n}" for n in sorted(only)]
        seen.update(only)
    for entry in marketplace_entries(repo):
        name = pathlib.PurePosixPath(entry).name
        if name not in seen:
            out.append(entry)
            seen.add(name)
    return out


def marketplace_matches_generated(repo: pathlib.Path) -> bool:
    """Whether the committed ordered routes exactly match generated output."""
    return marketplace_entries(repo) == generate_declarations(repo)


def render_marketplace(repo: pathlib.Path) -> str:
    """Render the marketplace with only the generated skill block replaced."""
    mp = repo / MARKETPLACE_PATH
    if not mp.is_file():
        raise FileNotFoundError(mp)
    doc = json.loads(mp.read_text(encoding="utf-8"))
    marketplace_plugin(doc)["skills"] = generate_declarations(repo)
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def write_marketplace(repo: pathlib.Path) -> bool:
    """Write generated declarations; return True only when bytes changed."""
    mp = repo / MARKETPLACE_PATH
    rendered = render_marketplace(repo)
    if mp.read_text(encoding="utf-8") == rendered:
        return False
    io.open(mp, "w", encoding="utf-8", newline="\n").write(rendered)
    return True


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
        "--write",
        action="store_true",
        help="replace the marketplace skill list with generated declarations",
    )
    ap.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="exit non-zero when drift exists (opt-in; see module docstring)",
    )
    a = ap.parse_args()

    repo = a.repo.resolve()
    try:
        c = census(repo)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"FAILED: cannot read skill index inputs: {exc}", file=sys.stderr)
        return 2

    if not c["control_enumerator_found_skills"]:
        print(
            f"FAILED: enumerator did not find known-present {KNOWN_PRESENT_SKILL!r} under "
            f"{CANONICAL_ROOT} — wrong --repo, moved control, or broken walk. Refusing to "
            "report drift from an unvalidated detector.",
            file=sys.stderr,
        )
        return 2

    try:
        if a.emit:
            print(json.dumps(generate_declarations(repo), indent=2))
            return 0
        if a.write:
            changed = write_marketplace(repo)
            print(
                "UPDATED: generated skill index"
                if changed
                else "OK: generated skill index already current"
            )
            return 0
        index_drift = not marketplace_matches_generated(repo)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"FAILED: cannot generate skill index: {exc}", file=sys.stderr)
        return 2

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

    if a.check:
        print(f"  INDEX DRIFT: {'yes' if index_drift else 'no'}")
    return 1 if (index_drift and a.fail_on_drift) else 0


if __name__ == "__main__":
    raise SystemExit(main())
