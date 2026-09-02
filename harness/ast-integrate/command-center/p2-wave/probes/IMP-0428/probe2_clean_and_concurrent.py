#!/usr/bin/env python3
"""Probe 2: clean-tree empty out-of-scope list; concurrent sibling writer.

Security reviewer on the refusal path: traversal, empty scope, commit -a,
and the cached-check mutation (verify_cached=False misses contamination;
the live check does not).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CC = REPO / "tools" / "command-center"
sys.path.insert(0, str(CC))

import index_scope_guard as G  # noqa: E402

UNIT = "IMP-0428"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="imp0428-p2-"))
    report: dict = {"probe": "probe2-clean-concurrent-refusal", "unit_id": UNIT}
    try:
        clean = G.init_scratch_repo(tmp / "clean")
        unit_rel, _sib = G.plant_unit_and_sibling(clean)
        scope = (unit_rel,)
        scoped = G.scoped_stage(clean, scope, [unit_rel])
        if not scoped.allowed:
            return fail(f"clean scoped add failed: {scoped.message}")
        G.git(clean, "commit", "-m", "unit only", check=True)
        after = G.inspect_index(clean, scope)
        report["clean_tree"] = after.to_dict()
        if after.out_of_scope:
            return fail(f"clean tree out_of_scope={after.out_of_scope}")
        if after.staged:
            return fail(f"clean tree still staged {after.staged}")
        if not after.allowed:
            return fail("clean tree inspect refused")

        live = G.init_scratch_repo(tmp / "live")
        unit_rel, sibling_rel = G.plant_unit_and_sibling(live)
        stop = threading.Event()
        seen = {"n": 0}

        def writer() -> None:
            d = live / "sibling"
            d.mkdir(exist_ok=True)
            n = 0
            while not stop.is_set():
                n += 1
                (d / f"live-{n}.txt").write_text(f"sib {n}\n", encoding="utf-8")
                seen["n"] = n
                time.sleep(0.005)

        thread = threading.Thread(target=writer, daemon=True)
        thread.start()
        deadline = time.time() + 2
        while seen["n"] < 5 and time.time() < deadline:
            time.sleep(0.01)
        staged = G.scoped_stage(live, (unit_rel,), [unit_rel])
        time.sleep(0.04)
        would = G.unguarded_broad_would_add(live)
        stop.set()
        thread.join(timeout=2)
        report["concurrent"] = {
            "sibling_writes_observed": seen["n"],
            "scoped": staged.to_dict(),
            "unguarded_broad_would_add": would,
        }
        if seen["n"] < 5:
            return fail(f"sibling writer too quiet n={seen['n']}")
        if not staged.allowed:
            return fail(f"concurrent scoped add refused: {staged.message}")
        if any(p.startswith("sibling/") for p in staged.staged):
            return fail(f"sibling leaked into staged set: {staged.staged}")
        if not any(p.startswith("sibling/live-") for p in would):
            return fail(f"broad dry-run missed live sibling files: {would}")
        if sibling_rel not in would:
            return fail("planted sibling absent from broad dry-run")

        trav = G.scoped_stage(live, (unit_rel,), ["../outside.txt"])
        empty = G.scoped_stage(live, (), [unit_rel])
        abs_p = G.scoped_stage(live, (unit_rel,), [str(tmp / "outside.txt")])
        commit_a = G.classify_commit_argv(["commit", "-a"])
        G.git(live, "add", "--", sibling_rel, check=True)
        vacuous = G.inspect_index(live, (unit_rel,), verify_cached=False)
        live_check = G.inspect_index(live, (unit_rel,), verify_cached=True)
        report["refusal_path"] = {
            "traversal": trav.to_dict(),
            "empty_scope": empty.to_dict(),
            "absolute_outside": abs_p.to_dict(),
            "commit_dash_a_broad": commit_a.to_dict(),
            "mutation_skip_cached_allows": vacuous.allowed,
            "live_cached_check_allows": live_check.allowed,
            "live_out_of_scope": live_check.out_of_scope,
        }
        if trav.code != G.Codes.TRAVERSAL:
            return fail(f"traversal code={trav.code}")
        if empty.code != G.Codes.EMPTY_SCOPE:
            return fail(f"empty scope code={empty.code}")
        if abs_p.code != G.Codes.TRAVERSAL:
            return fail(f"absolute outside code={abs_p.code}")
        if not commit_a.broad:
            return fail("commit -a not classified broad")
        if not vacuous.allowed:
            return fail("mutation control did not go vacuous")
        if live_check.allowed or sibling_rel not in live_check.out_of_scope:
            return fail("live cached check missed contamination")

        report["pass"] = True
        print(json.dumps(report, indent=2, sort_keys=True))
        print(
            f"SUCCESS:{UNIT}-probe2 clean oos empty; concurrent sibling excluded; "
            "refusal path traversal/empty-scope/commit-a; cached-check mutation fires"
        )
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
