#!/usr/bin/env python3
"""F4 independent probe.

MECHANICALLY DIFFERENT from the anchor:
  anchor  = scratch working-tree clone + run `gen_skill_index.py --check --fail-on-drift`,
            read stdout census text + process exit code.
  here    = read the tree from the GIT OBJECT DATABASE (`git ls-tree`, `git cat-file`) at a
            pinned rev, never the working tree; re-implement the declaration-ordering
            algorithm independently; compare ORDERED PYTHON LISTS in-process. No subprocess
            exit code is consulted, no census line is parsed.

Detector controls:
  C1 known-present: '010-editor' must appear under the canonical root.
  C2 both-states  : the comparator must report EQUAL at baseline and UNEQUAL for a
                    deliberately corrupted list. A comparator that never fires measures nothing.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REV = "53c37c6c"
REPO = pathlib.Path(r"C:/Users/Prekzursil/source/ast-integrate")
CANONICAL_ROOT = ".agents/skills"
PROJECTION_ROOTS = ("skills", "skills-claude-only")
STUBS = [
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout


def tree_paths() -> list[str]:
    return [p for p in git("ls-tree", "-r", "--name-only", REV).splitlines() if p]


def skills_under(paths: list[str], root: str) -> set[str]:
    pref = root + "/"
    out = set()
    for p in paths:
        if p.startswith(pref) and p.endswith("/SKILL.md"):
            rest = p[len(pref) : -len("/SKILL.md")]
            if "/" not in rest:
                out.add(rest)
    return out


def marketplace_doc() -> dict:
    return json.loads(git("cat-file", "-p", f"{REV}:.claude-plugin/marketplace.json"))


def plugin_skills(doc: dict) -> list[str]:
    name = doc.get("name")
    matches = [
        p for p in doc["plugins"] if isinstance(p, dict) and p.get("name") == name
    ]
    assert len(matches) == 1, f"expected 1 self-named plugin, got {len(matches)}"
    return list(matches[0]["skills"])


def generate(
    canonical: set[str], projections: dict[str, set[str]], declared_routes: list[str]
) -> list[str]:
    """Independent re-implementation of ci/gen_skill_index.generate_declarations."""
    out = [f"./{CANONICAL_ROOT}/{n}" for n in sorted(canonical)]
    seen = set(canonical)
    for root in PROJECTION_ROOTS:
        only = sorted(projections.get(root, set()) - seen)
        out += [f"./{root}/{n}" for n in only]
        seen.update(only)
    for entry in declared_routes:
        nm = entry.rsplit("/", 1)[-1]
        if nm not in seen:
            out.append(entry)
            seen.add(nm)
    return out


def state(
    label: str,
    del_dirs: bool,
    prune_manifest: bool,
    paths: list[str],
    base_routes: list[str],
) -> dict:
    canonical = skills_under(paths, CANONICAL_ROOT)
    projections = {r: skills_under(paths, r) for r in PROJECTION_ROOTS}
    routes = list(base_routes)
    if del_dirs:
        canonical -= set(STUBS)
        for r in projections:
            projections[r] -= set(STUBS)
    if prune_manifest:
        routes = [e for e in routes if e.rsplit("/", 1)[-1] not in set(STUBS)]

    gen = generate(canonical, projections, routes)
    on_disk = set(canonical)
    for v in projections.values():
        on_disk |= v
    declared_names = {e.rsplit("/", 1)[-1] for e in routes}
    drift = gen != routes
    # first index where they diverge, for evidence
    first_div = None
    for i in range(max(len(gen), len(routes))):
        g = gen[i] if i < len(gen) else "<none>"
        m = routes[i] if i < len(routes) else "<none>"
        if g != m:
            first_div = (i, m, g)
            break
    return {
        "state": label,
        "declared_count": len(declared_names),
        "on_disk_union": len(on_disk),
        "dangling_declared_but_absent": len(declared_names - on_disk),
        "undeclared_on_disk": len(on_disk - declared_names),
        "canonical_not_declared": len(canonical - declared_names),
        "INDEX_DRIFT": drift,
        "implied_exit_with_fail_on_drift": 1 if drift else 0,
        "first_divergence_idx_marketplace_vs_generated": first_div,
    }


def main() -> int:
    paths = tree_paths()
    doc = marketplace_doc()
    base_routes = plugin_skills(doc)

    canonical = skills_under(paths, CANONICAL_ROOT)
    control_known_present = "010-editor" in canonical
    stubs_present_canonical = sorted(set(STUBS) & canonical)
    stubs_in_projections = {
        r: sorted(set(STUBS) & skills_under(paths, r)) for r in PROJECTION_ROOTS
    }

    # where do the stub routes sit in the published list?
    stub_positions = {
        e: i for i, e in enumerate(base_routes) if e.rsplit("/", 1)[-1] in set(STUBS)
    }

    # every plugin's skills vs the self-named plugin's skills
    all_plugin_names = [p.get("name") for p in doc["plugins"]]

    results = [
        state("0-baseline", False, False, paths, base_routes),
        state("A-dirs-only", True, False, paths, base_routes),
        state("C-manifest-only", False, True, paths, base_routes),
        state("B-both", True, True, paths, base_routes),
    ]

    # C2 both-states control: comparator must fire on a deliberate corruption
    corrupted = list(base_routes)
    corrupted[0], corrupted[1] = corrupted[1], corrupted[0]
    control_fires = corrupted != base_routes

    print(
        json.dumps(
            {
                "rev": REV,
                "control_known_present_010-editor_in_canonical": control_known_present,
                "control_comparator_fires_on_corruption": control_fires,
                "marketplace_plugin_names": all_plugin_names,
                "published_route_count": len(base_routes),
                "published_routes_unique": len(set(base_routes)) == len(base_routes),
                "canonical_count": len(canonical),
                "stubs_present_in_canonical": stubs_present_canonical,
                "stubs_present_in_projections": stubs_in_projections,
                "stub_route_positions_in_published_list": stub_positions,
                "stub_routes_published_as": sorted(
                    e for e in base_routes if e.rsplit("/", 1)[-1] in set(STUBS)
                ),
                "last_5_published_routes": base_routes[-5:],
                "states": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
