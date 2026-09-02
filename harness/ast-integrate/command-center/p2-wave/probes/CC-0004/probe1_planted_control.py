#!/usr/bin/env python3
"""Probe 1: planted-control + known-present import site (function-shaped fork)."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CC-0004-probe1 {msg}")
    return 1


def locators(rows: list[dict]) -> set[str]:
    return {D.locator(r) for r in rows}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cc0004-p1-") as tmp:
        root = Path(tmp)
        meta = F.write_clean_tree(root)
        clean = D.scan(root, skip_prefixes=())
        if clean["fork_count"] != 0:
            return fail(f"clean tree not silent forks={clean['forks']}")
        resolved = locators(clean["resolved"])
        want_resolved = f"{meta['resolved_rel']}:{meta['resolved_line']}:{meta['resolved_name']}"
        if want_resolved not in resolved:
            return fail(f"known-present missing {want_resolved} got={sorted(resolved)}")
        canonical = locators(clean["canonical"])
        want_canon = (
            f"{meta['canonical_rel']}:{meta['canonical_line']}:evaluate_completion"
        )
        if want_canon not in canonical:
            return fail(f"canonical missing {want_canon} got={sorted(canonical)}")
        mention_hits = [
            h
            for h in clean["forks"] + clean["resolved"] + clean["canonical"]
            if h["path"] in {meta["mention_py"], meta["mention_md"]}
        ]
        if mention_hits:
            return fail(f"mention files fired {mention_hits}")

        plant = F.plant_function_fork(root)
        planted = D.scan(root, skip_prefixes=())
        fork_locs = locators(planted["forks"])
        want_fork = f"{plant['plant_rel']}:{plant['plant_line']}:{plant['plant_name']}"
        if want_fork not in fork_locs:
            return fail(f"plant did not fire {want_fork} got={sorted(fork_locs)}")
        if planted["fork_count"] != 1:
            return fail(f"expected exactly one fork got={planted['forks']}")
        if want_resolved not in locators(planted["resolved"]):
            return fail("known-present vanished after plant")

    print(
        f"clean_silent=True known_present={want_resolved} "
        f"plant_fired={want_fork} mention_silent=True method=ast-import-graph"
    )
    print("SUCCESS:CC-0004-probe1 planted-control function-shape")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
