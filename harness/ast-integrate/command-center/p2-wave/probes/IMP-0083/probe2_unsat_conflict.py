#!/usr/bin/env python3
"""Probe 2: UNSAT conflicting pair + set-iteration negative control (IMP-0083)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace import scenarios as S  # noqa: E402
from marketplace.resolver import (  # noqa: E402
    resolve,
    resolve_order_sensitive,
    resolve_set_iteration,
    solution_digest,
)
from marketplace.version import satisfies  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0083.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0083-probe2 {msg}")
    return 1


def main() -> int:
    result = resolve(S.unsat_conflict_index(), S.unsat_conflict_request())
    print(f"unsat_status={result.status} pair={result.conflicting_pair}")
    if result.status != "UNSATISFIABLE":
        return fail("conflict fixture was not UNSATISFIABLE")
    if result.solution:
        return fail("UNSAT silently returned a solution")
    pair = result.conflicting_pair or []
    if len(pair) != 2:
        return fail(f"expected 2-row pair, got {pair}")
    if {row["package"] for row in pair} != {"shared"}:
        return fail(f"pair not about shared: {pair}")
    if sorted(row["range"] for row in pair) != ["^1.0.0", "^2.0.0"]:
        return fail(f"unexpected ranges {pair}")
    sources = {row["source"] for row in pair}
    if "foo@1.0.0" not in sources or "bar@1.0.0" not in sources:
        return fail(f"sources missing foo/bar: {sources}")

    both = [
        v
        for v in ("1.0.0", "1.1.0", "2.0.0", "2.1.0")
        if satisfies("^1.0.0", v) and satisfies("^2.0.0", v)
    ]
    if both:
        return fail(f"catalog unexpectedly has a version satisfying both: {both}")

    single = resolve(
        S.single_constraint_unsat_index(), [{"name": "only", "range": "^9.0.0"}]
    )
    print(f"single_status={single.status} pair={single.conflicting_pair}")
    if single.status != "UNSATISFIABLE":
        return fail("single-constraint unsat was not UNSATISFIABLE")
    sp = single.conflicting_pair or []
    if len(sp) != 2 or sp[0]["source"] != "root" or sp[1]["source"] != "index":
        return fail(f"single-constraint pair malformed {sp}")
    if sp[1]["range"] != "no-satisfying-version":
        return fail(f"expected index sentinel, got {sp}")

    index = S.sat_diamond_index()
    request = S.sat_diamond_request()
    set_seen = set()
    order_seen = set()
    for seed in range(30):
        shuffled = S.shuffle_index(index, seed)
        set_seen.add(solution_digest(resolve_set_iteration(shuffled, request)))
        order_seen.add(solution_digest(resolve_order_sensitive(shuffled, request)))
    print(f"neg_set_distinct={len(set_seen)} neg_order_distinct={len(order_seen)}")
    if len(set_seen) < 2:
        return fail("NEGATIVE CONTROL: set-iteration foil was shuffle-invariant")
    if len(order_seen) < 2:
        return fail("NEGATIVE CONTROL: first-listed foil was shuffle-invariant")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:IMP-0083" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    print("SUCCESS:IMP-0083-probe2 unsat-pair-and-negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
