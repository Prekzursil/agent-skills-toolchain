#!/usr/bin/env python3
"""Probe 2: independent set difference, plus one-directional mutant.

Mechanically different from probe 1:
  * Probe 1 calls detect() which parses SKILL.md frontmatter.
  * This probe enumerates capability_id as skill:<parent-dir> via rglob
    of SKILL.md filenames only — no frontmatter parse, no detect().

The two sets must agree. A one-directional (repo minus live) helper must
miss the planted live-only id, proving the bidirectional detector is the
thing that closes failure class one-directional-comparison.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def load_presence_gap():
    path = REPO / "tools" / "router" / "presence_gap.py"
    spec = importlib.util.spec_from_file_location("imp0401_presence_gap", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def dir_name_ids(root: Path) -> set[str]:
    """Independent enumerator: directory name of each SKILL.md, no YAML."""
    ids: set[str] = set()
    if not root.is_dir():
        return ids
    for p in root.rglob("SKILL.md"):
        if p.is_file():
            ids.add("skill:" + p.parent.name)
    return ids


def main() -> int:
    sys.path.insert(0, str(HERE))
    import fixtures as F  # noqa: E402

    pg = load_presence_gap()

    repo_ids: set[str] = set()
    live_ids: set[str] = set()
    for root in F.fixture_repo_roots():
        repo_ids |= dir_name_ids(root)
    for root in F.fixture_live_roots():
        live_ids |= dir_name_ids(root)

    indep_repo_only = sorted(repo_ids - live_ids)
    indep_live_only = sorted(live_ids - repo_ids)
    indep_both = sorted(repo_ids & live_ids)

    if F.PLANTED_REPO_ONLY not in indep_repo_only:
        print(f"FAILED:IMP-0401-probe2 independent repo-only missing {indep_repo_only}")
        return 1
    if F.PLANTED_LIVE_ONLY not in indep_live_only:
        print(f"FAILED:IMP-0401-probe2 independent live-only missing {indep_live_only}")
        return 1
    if F.PLANTED_BOTH in indep_repo_only or F.PLANTED_BOTH in indep_live_only:
        print("FAILED:IMP-0401-probe2 independent both leaked into a gap list")
        return 1
    if set(indep_repo_only) & set(indep_live_only):
        print("FAILED:IMP-0401-probe2 independent lists not disjoint")
        return 1

    # Compare against detect() — disagreement is BLOCKED, not a picked winner.
    report = pg.detect(F.fixture_repo_roots(), F.fixture_live_roots(), index=F.INDEX_PATH)
    if indep_repo_only != report["repo_only"] or indep_live_only != report["live_only"]:
        print("FAILED:IMP-0401-probe2 independent set-diff disagrees with detect()")
        print(json.dumps({"independent": {"repo_only": indep_repo_only, "live_only": indep_live_only}, "detect": {"repo_only": report["repo_only"], "live_only": report["live_only"]}}))
        return 1
    if indep_both != report["both"]:
        print("FAILED:IMP-0401-probe2 independent both disagrees with detect()")
        return 1

    one_way = pg.one_directional_repo_minus_live(repo_ids, live_ids)
    if F.PLANTED_LIVE_ONLY in one_way:
        print("FAILED:IMP-0401-probe2 one-directional mutant unexpectedly saw live-only")
        return 1
    if F.PLANTED_LIVE_ONLY not in indep_live_only:
        print("FAILED:IMP-0401-probe2 live-only vanished before mutant check")
        return 1
    if F.PLANTED_REPO_ONLY not in one_way:
        print("FAILED:IMP-0401-probe2 one-directional mutant missed repo-only")
        return 1

    payload = {
        "probe": "probe2-independent-setdiff",
        "unit_id": "IMP-0401",
        "pass": True,
        "independent_method": "rglob-SKILL.md-parent-directory-name",
        "detect_method": report["method"],
        "agree": True,
        "repo_only": indep_repo_only,
        "live_only": indep_live_only,
        "both": indep_both,
        "one_directional_misses_live_only": True,
        "one_directional_repo_minus_live": one_way,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "agree=True independent_repo_only="
        + ",".join(indep_repo_only)
        + " independent_live_only="
        + ",".join(indep_live_only)
        + " one_way_misses_live_only=True"
    )
    print("SUCCESS:IMP-0401-probe2 independent set-diff and one-directional mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
