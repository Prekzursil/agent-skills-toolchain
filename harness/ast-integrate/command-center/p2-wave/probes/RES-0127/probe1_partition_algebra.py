#!/usr/bin/env python3
"""Probe 1: three-way partition algebra + identical-bytes exactly-one-bucket.

Recomputes the control (and live) partitions from directory listings. Does not
trust the receipt's counts without rebuilding them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from control_trees import EXPECTED, ensure_control_trees  # noqa: E402
from locate import locate_trees  # noqa: E402
from partition import (  # noqa: E402
    ABSENT_SENTINEL,
    mutate_identical_into_different,
    partition_trees,
    proof_of,
)

ART = REPO / "command-center" / "research" / "RES-0127.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0127-probe1 {msg}")
    return 1


def main() -> int:
    ctrl_a, ctrl_b = ensure_control_trees()
    control = partition_trees(ctrl_a, ctrl_b)
    proof = control["proof"]
    if not proof["ok"]:
        return fail(f"control proof {proof}")
    if control["index"] != EXPECTED:
        return fail(f"control index {control['index']} != {EXPECTED}")
    ident = control["index"]["in_both_identical"]
    if ident != ["control-identical.md"]:
        return fail(f"identical bucket {ident}")
    for rel in ident:
        n = sum(rel in control["index"][k] for k in control["index"])
        if n != 1:
            return fail(f"{rel} in {n} buckets")
    if ABSENT_SENTINEL in set().union(*control["index"].values()):
        return fail("absent sentinel invented")

    mutant = mutate_identical_into_different(control)
    mproof = proof_of(mutant, control["hashed_a"], control["hashed_b"])
    if mproof["ok"] or mproof["pairwise_disjoint"]:
        return fail("mutant silent")
    if not proof["identical_disjoint_from_different"]:
        return fail("identical not disjoint from different")

    located = locate_trees()
    live_a = (
        Path(located["platform_redesign"]["root"])
        if located["platform_redesign"]["present"]
        else None
    )
    live_b = (
        Path(located["harness_restore"]["root"])
        if located["harness_restore"]["present"]
        else None
    )
    live = partition_trees(live_a, live_b)
    if not live["proof"]["ok"]:
        return fail(f"live proof {live['proof']}")

    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if "SUCCESS:RES-0127" not in text:
        return fail("sentinel absent")
    needle = (
        "a computed three-way partition with hashes, where the "
        "in-both-identical bucket is disjoint from the differing bucket"
    )
    if needle not in text:
        return fail("completion phrase absent")

    published = (doc.get("registry") or {}).get("control") or {}
    pub_part = published.get("partition") or {}
    pub_idx = pub_part.get("index")
    if pub_idx != control["index"]:
        return fail(f"published control index drifted {pub_idx}")
    pub_proof = pub_part.get("proof") or {}
    if not pub_proof.get("ok"):
        return fail("published control proof not ok")
    if not pub_proof.get("identical_disjoint_from_different"):
        return fail("published identical/different not disjoint")

    live_pub = (doc.get("registry") or {}).get("live") or {}
    live_idx = live_pub.get("index")
    if live_idx != live["index"]:
        return fail(f"published live index drifted {live_idx}")
    art_both = bool(
        ((doc.get("registry") or {}).get("live_trees") or {}).get("both_present")
    )
    if art_both != located["both_present"]:
        return fail(
            f"live_trees.both_present dishonest art={art_both} live={located['both_present']}"
        )
    if not located["both_present"] and live["counts"]["union"] != 0:
        return fail("absent live trees produced a non-empty live union")

    three = doc.get("three_way_partition_with_hashes") or {}
    if not three.get("in_both_identical_disjoint_from_differing"):
        return fail("top-level disjoint flag false")

    payload = {
        "pass": True,
        "probe": "probe1-partition-algebra",
        "control_counts": control["counts"],
        "live_counts": live["counts"],
        "live_both_present": located["both_present"],
        "mutant_fired": True,
        "identical_exactly_one_bucket": True,
        "pairwise_disjoint": True,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"control union={control['counts']['union']} "
        f"identical={control['counts']['in_both_identical']} "
        f"different={control['counts']['in_both_different']} "
        f"live_union={live['counts']['union']}"
    )
    print("SUCCESS:RES-0127-probe1 partition algebra")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
