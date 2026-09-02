#!/usr/bin/env python3
"""Probe 1: emitted fusion has 0 unreachable branches (computed, two derivations).

Signal 1: dual_reachability reports unreachable == [] and the two derivations
agree. Signal 2 (runtime): every well-typed assignment routes to exactly one
source, and every declared branch including default is exercised.

The catalog artifact must already exist (measure writes-then-probes order);
this probe re-computes reachability from the live operator, it does not trust
the receipt's copied numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(HERE))

from workflow_fusion.conditional_hybrid import (  # noqa: E402
    emit_conditional_hybrid,
    route,
)
from workflow_fusion.reachability import dual_reachability, proofs_agree  # noqa: E402
from workflow_fusion.typed_predicate import eval_pred, typed_universe  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0186.json"
FUSION = REPO / "command-center/fusion/IMP-0186-conditional-hybrid.json"
UNIT = "IMP-0186"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    spec = S.good_spec()
    proof = dual_reachability(spec)
    if not proof.agreement:
        return fail(
            f"derivation disagreement cfg={list(proof.cfg_reachable)} "
            f"bitmask={list(proof.bitmask_reachable)}"
        )
    if not proofs_agree(proof):
        return fail("proofs_agree reconstructed disagreement")
    if proof.unreachable:
        return fail(f"unreachable={list(proof.unreachable)}")
    if proof.unrouted_count != 0:
        return fail(f"unrouted_count={proof.unrouted_count}")
    if proof.universe_size != 18:
        return fail(f"universe_size={proof.universe_size} want 3*2*3=18")

    fusion = emit_conditional_hybrid(spec)
    if fusion["default_branch_id"] != "br.default" or not fusion["default_explicit"]:
        return fail("default branch not explicit")
    if any(not b["reachable"] or b["witness"] is None for b in fusion["branches"]):
        return fail("emitted branch missing witness")

    universe = typed_universe(spec["input_type"])
    counts: dict[str, int] = {br["id"]: 0 for br in spec["branches"]}
    for env in universe:
        src = route(fusion, env)
        # Cross-check first-match on the spec independently of the fused record.
        src2 = route(spec, env)
        if src != src2:
            return fail(f"route(fusion)={src} route(spec)={src2} env={env}")
        owner = None
        for br in spec["branches"]:
            if eval_pred(br["predicate"], env):
                owner = br["id"]
                break
        if owner is None:
            return fail(f"unrouted at runtime env={env}")
        counts[owner] += 1
        want_src = next(b["source_id"] for b in spec["branches"] if b["id"] == owner)
        if src != want_src:
            return fail(f"source mismatch owner={owner} src={src}")

    if any(v == 0 for v in counts.values()):
        return fail(f"unexercised branches {counts}")
    if sum(counts.values()) != len(universe):
        return fail(f"assignment total {sum(counts.values())} != {len(universe)}")

    # Detector control on the agreement check: drop one reachable id and
    # require proofs_agree to fail. A checker that still returns True is inert.
    corrupted = proof.__class__(
        universe_size=proof.universe_size,
        cfg_reachable=proof.cfg_reachable[:-1],
        bitmask_reachable=proof.bitmask_reachable,
        unreachable=proof.unreachable,
        unrouted_count=proof.unrouted_count,
        unrouted_witness=proof.unrouted_witness,
        agreement=True,
        hits=proof.hits,
        assignment_owner=proof.assignment_owner,
    )
    if proofs_agree(corrupted):
        return fail("proofs_agree silent on truncated cfg_reachable")

    if not ART.is_file():
        return fail("receipt missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:IMP-0186" not in blob:
        return fail("sentinel absent from receipt")
    if not FUSION.is_file():
        return fail("fusion artifact missing")
    live = json.loads(FUSION.read_text(encoding="utf-8"))
    if live.get("reachability_proof", {}).get("unreachable") != []:
        return fail("live fusion proof lists unreachable branches")
    if live.get("id") != fusion["id"]:
        return fail("live fusion id drifted from re-emit")

    report = {
        "probe": "probe1-zero-unreachable",
        "unit_id": UNIT,
        "pass": True,
        "universe_size": proof.universe_size,
        "unreachable": [],
        "unrouted_count": 0,
        "agreement": True,
        "branch_taken_counts": counts,
        "default_branch_id": fusion["default_branch_id"],
        "default_explicit": True,
        "default_taken": counts["br.default"],
        "cfg_reachable": list(proof.cfg_reachable),
        "bitmask_reachable": list(proof.bitmask_reachable),
        "agreement_mutant_fired": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        f"unreachable=0 universe={proof.universe_size} "
        f"default_taken={counts['br.default']} agreement=True"
    )
    print("SUCCESS:IMP-0186-probe1 0 unreachable branches (computed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
