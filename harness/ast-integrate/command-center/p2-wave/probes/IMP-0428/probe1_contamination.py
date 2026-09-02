#!/usr/bin/env python3
"""Probe 1: planted sibling — broad add refused; scoped add excludes it.

Both-states control: the same tree under unguarded ``git add -A`` really
does stage the sibling (so the refusal is not a vacuous no-op).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
sys.path.insert(0, str(CC))

import index_scope_guard as G  # noqa: E402

UNIT = "IMP-0428"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0428-p1-"))
    report: dict = {"probe": "probe1-contamination", "unit_id": UNIT}
    try:
        repo = G.init_scratch_repo(tmp / "guarded")
        unit_rel, sibling_rel = G.plant_unit_and_sibling(repo)
        scope = (unit_rel,)

        would = G.unguarded_broad_would_add(repo)
        report["unguarded_dry_run_would_add"] = would
        if sibling_rel not in would:
            return fail(f"dry-run control did not list sibling: {would}")

        clone = G.init_scratch_repo(tmp / "unguarded")
        G.plant_unit_and_sibling(clone)
        G.git(clone, "add", "-A", check=True)
        unguarded_cached = G.cached_paths(clone)
        report["unguarded_cached"] = unguarded_cached
        if sibling_rel not in unguarded_cached:
            return fail("unguarded git add -A did not stage sibling (vacuous control)")

        refusals = []
        before = G.cached_paths(repo)
        for argv in (
            ("add", "-A"),
            ("git", "add", "--all"),
            ("add", "."),
            ("add", "-u"),
        ):
            result = G.scoped_stage(repo, scope, [], argv=argv)
            refusals.append(
                {
                    "argv": list(argv),
                    "allowed": result.allowed,
                    "code": result.code,
                    "cached_after": G.cached_paths(repo),
                }
            )
            if result.allowed:
                return fail(f"broad {argv} was allowed")
            if result.code != G.Codes.BROAD_STAGE:
                return fail(f"broad {argv} code={result.code}")
            if G.cached_paths(repo) != before:
                return fail(f"broad {argv} mutated the index")
        report["broad_refusals"] = refusals

        scoped = G.scoped_stage(repo, scope, [unit_rel])
        report["scoped"] = scoped.to_dict()
        if not scoped.allowed:
            return fail(f"scoped add refused: {scoped.message}")
        if unit_rel not in scoped.staged:
            return fail("scoped add did not stage the unit file")
        if sibling_rel in scoped.staged:
            return fail("scoped add staged the sibling")
        if scoped.out_of_scope:
            return fail(f"scoped add out_of_scope={scoped.out_of_scope}")

        G.git(repo, "add", "--", sibling_rel, check=True)
        offered = G.offer_commit(repo, scope)
        report["precontaminated_offer"] = offered.to_dict()
        if offered.allowed or offered.commit_offered:
            return fail("commit offered on contaminated index")
        if sibling_rel not in offered.out_of_scope:
            return fail("contaminated sibling not listed")
        if sibling_rel not in G.cached_paths(repo):
            return fail("guard auto-corrected (unstaged) the sibling")
        if offered.auto_corrected:
            return fail("auto_corrected flag set")

        staged_vs_scope = {
            "declared_scope": list(scope),
            "cached": G.cached_paths(repo),
            "out_of_scope": offered.out_of_scope,
            "in_scope_staged": offered.in_scope_staged,
        }
        report["staged_set_versus_declared_scope"] = staged_vs_scope
        report["pass"] = True
        print(json.dumps(report, indent=2, sort_keys=True))
        print(
            f"SUCCESS:{UNIT}-probe1 broad refused; scoped excluded sibling; "
            f"unguarded -A staged it; contamination listed {offered.out_of_scope}"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
