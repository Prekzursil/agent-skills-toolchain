#!/usr/bin/env python3
"""Probe 1: both-states per invariant — each mutation turns exactly that one red."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import graphs as G  # noqa: E402
import suite as S  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0082-graph-invariant-suite.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0082-probe1 {msg}")
    return 1


def main() -> int:
    bundle, surface = G.load_eval_bundle()
    bat = S.mutation_battery(bundle)
    print(f"eval_surface={surface}")
    print(f"baseline_all_green={bat['baseline_all_green']}")
    for row in bat["mutations"]:
        print(
            f"mut={row['id']} target={row['target_invariant']} "
            f"red={row['red_set']} exactly_one={row['exactly_one_red']}"
        )
        if not row["pass"]:
            return fail(
                f"independence-broken {row['id']} red={row['red_set']} "
                f"want={[row['target_invariant']]}"
            )
    if not bat["mutation_independence"]:
        return fail("mutation_independence false")
    if bat["n_mutations_passed"] != 5:
        return fail(f"n_passed={bat['n_mutations_passed']}")

    live = G.live_status()
    n_live = sum(1 for v in live.values() if v["present"])
    print(f"live_v2_present={n_live}/4")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact-missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0082" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    rec = doc.get("mutation_records") or []
    if len(rec) != 5:
        return fail(f"artifact-mutation-count {len(rec)}")
    for row in rec:
        if not row.get("exactly_one_red"):
            return fail(f"artifact-row-not-independent {row.get('id')}")
        if not row.get("mutant_red"):
            return fail(f"artifact-row-not-live {row.get('id')}")
    invs = doc.get("invariants") or []
    if len(invs) != 5:
        return fail(f"artifact-invariant-count {len(invs)}")
    for inv in invs:
        if not inv.get("baseline_green"):
            return fail(f"artifact-baseline-not-green {inv.get('id')}")
        if not inv.get("mutation"):
            return fail(f"green-without-mutation-record {inv.get('id')}")
    crlf = S.crlf_roundtrip_stable(bundle)
    print(f"crlf_stable={crlf['stable']}")
    if not crlf["stable"]:
        return fail("crlf-verdict-diverged")
    print("SUCCESS:WFA-0082-probe1 mutation-independence both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
