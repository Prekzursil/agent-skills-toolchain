#!/usr/bin/env python3
"""Probe 2: independent recount (Kahn + set difference) of the same battery."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graphs as G  # noqa: E402
import recount as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0082-graph-invariant-suite.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0082-probe2 {msg}")
    return 1


def main() -> int:
    bundle, surface = G.load_eval_bundle()
    bat = R.battery(bundle)
    print(f"eval_surface={surface}")
    print(f"recount_baseline={json.dumps(bat['baseline'], sort_keys=True)}")
    for row in bat["rows"]:
        print(
            f"recount target={row['target']} red={row['red_set']} "
            f"exactly={row['exactly_that']}"
        )
        if not row["exactly_that"]:
            return fail(f"recount-not-independent {row}")
    if not bat["pass"]:
        return fail("recount-battery-failed")

    if not ART.is_file():
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0082" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    art_red = {
        row["target_invariant"]: list(row.get("red_set") or [])
        for row in doc.get("mutation_records") or []
    }
    for row in bat["rows"]:
        recorded = art_red.get(row["target"])
        if recorded != row["red_set"]:
            return fail(
                f"artifact-recount-disagree target={row['target']} "
                f"artifact={recorded} recount={row['red_set']}"
            )
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") not in {"PASS", "PENDING"}:
        return fail(f"reviewer-verdict {reviewer.get('verdict')}")
    print("SUCCESS:WFA-0082-probe2 independent-recount Kahn-acyclicity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
