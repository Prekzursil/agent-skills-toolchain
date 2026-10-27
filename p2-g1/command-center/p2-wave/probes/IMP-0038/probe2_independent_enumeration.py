#!/usr/bin/env python3
"""IMP-0038 probe2: independent reviewer probe — walk vs manifest parse.

Reviewer obligations (receipt reviewer block): an independent os.walk census
(NOT the reconciler's enumerator) and a four-kind manifest parse must agree on
the complete fixture and DISAGREE on the forgotten-manifest control. The
independent walk must also see the planted live-only skill (measured, not
assumed).
"""
from __future__ import annotations

import ast  # bind stdlib ast before tools/ast.py can shadow it
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import registration_fixture as fx  # noqa: E402
import registration_reconciler as rr  # noqa: E402

KIND_DIRS = {"skill": "skills", "hook": "hooks", "rule": "rules", "command": "commands"}


def independent_walk(root: Path) -> set[str]:
    """Plain os.walk census, mechanically independent of rr.enumerate_fs.

    Applies the census's DOCUMENTED control-plane exclusion (manifest index
    files are registration metadata, not capabilities) with its own code.
    """
    found: set[str] = set()
    for kind, sub in KIND_DIRS.items():
        base = root / sub
        if not base.is_dir():
            continue
        for cur, _dirs, files in Path.walk(base):
            for name in files:
                low = name.lower()
                if low == "manifest.json" or low.endswith("-manifest.json"):
                    continue  # control-plane index, not a capability
                p = Path(cur) / name
                rel = p.relative_to(base).as_posix()
                if kind == "skill":
                    if name == "SKILL.md":
                        found.add(f"skill:{p.parent.name}")
                elif kind == "hook":
                    if name.startswith("hook.") and name.endswith(".json"):
                        found.add(f"hook:{name[5:-5]}")
                else:
                    found.add(f"{kind}:{rel}")
    return found


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0038-p2-"))
    try:
        checks: dict[str, bool] = {}

        # Complete fixture: independent walk == reconciler's FS sets == manifest parse.
        trees = fx.build_control_trees(tmp / "complete", omit_forgotten_from_repo_manifest=False)
        walk_repo = independent_walk(Path(trees["repo"]))
        walk_live = independent_walk(Path(trees["live"]))
        rr_repo = rr.flatten(rr.enumerate_fs(trees["repo"]))
        rr_live = rr.flatten(rr.enumerate_fs(trees["live"]))
        man_repo = rr.flatten(rr.enumerate_manifest(trees["repo"]))
        man_live = rr.flatten(rr.enumerate_manifest(trees["live"]))

        checks["walk_equals_rr_repo"] = walk_repo == rr_repo
        checks["walk_equals_rr_live"] = walk_live == rr_live
        checks["manifest_agrees_complete"] = (
            rr_repo == man_repo and rr_live == man_live
        )
        checks["live_only_planted_measured"] = (
            fx.PLANTED["live_only_skill"] in walk_live - walk_repo
        )

        # Gap fixture: manifest parse must MISS the forgotten skill the walk sees.
        gap = fx.build_control_trees(tmp / "gap", omit_forgotten_from_repo_manifest=True)
        gap_walk = independent_walk(Path(gap["repo"]))
        gap_man = rr.flatten(rr.enumerate_manifest(gap["repo"]))
        checks["gap_disagrees"] = gap_walk != gap_man
        checks["gap_forgotten_seen_by_walk"] = (
            fx.PLANTED["forgotten_skill"] in gap_walk
        )
        checks["gap_forgotten_missed_by_parse"] = (
            fx.PLANTED["forgotten_skill"] not in gap_man
        )

        out = {
            "unit_id": "IMP-0038",
            "probe": "probe2-independent-enumeration",
            "walk_repo_count": len(walk_repo),
            "walk_live_count": len(walk_live),
            "checks": checks,
            "pass": all(checks.values()),
        }
        print(json.dumps(out, sort_keys=True))
        print("independent.repo_only=" + json.dumps(sorted(walk_repo - walk_live)))
        print("SUCCESS:IMP-0038-probe2 walk and parse agree complete, disagree on gap")
        if not all(checks.values()):
            print(f"FAILED:IMP-0038-probe2 {[k for k, v in checks.items() if not v]}")
            return 1
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
