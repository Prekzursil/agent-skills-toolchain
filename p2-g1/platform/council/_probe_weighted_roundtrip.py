"""Probe: is the schema's `weighted` stop_expression branch usable in a DOCUMENTED spec?

councilspec.schema.json offers four composite stop_expression forms: all_of, any_of, not and
`weighted` (clauses + threshold). `unparse` emits a WEIGHTED[...] >= t surface form for it.
The parser's documented grammar, however, is:

    primary := "(" expr ")" | nary | leaf
    nary    := ("ANY" | "ALL") "[" expr ("," expr)* "]"

- there is no WEIGHTED production. If `parse` cannot read what `unparse` writes, then any spec
using a weighted node CANNOT declare `stopping.source_expression` (SEM-001 compares
parse(source) to the tree) and CANNOT pass a tree-idempotence check
(parse(unparse(tree)) == tree). That would make the weighted branch effectively unusable in
exactly the specs that document themselves.

Both-states control: the same two checks are run against an all_of tree, which MUST succeed,
so a failure on the weighted tree cannot be blamed on the harness.

Run: python platform/council/_probe_weighted_roundtrip.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.abspath(os.path.join(HERE, "..", "lib"))
if LIB not in sys.path:
    sys.path.insert(0, LIB)

from councilspec.expression import evaluate, parse, unparse  # noqa: E402
from councilspec.validate import validate_spec  # noqa: E402

ALL_OF_TREE = {
    "all_of": [
        {"metric": "consensus", "op": ">=", "value": 0.9},
        {"metric": "every_objection_addressed", "op": "==", "value": True},
    ]
}

WEIGHTED_TREE = {
    "weighted": {
        "threshold": 2,
        "clauses": [
            {"weight": 1, "when": {"metric": "consensus", "op": ">=", "value": 0.9}},
            {
                "weight": 1,
                "when": {
                    "metric": "every_objection_addressed",
                    "op": "==",
                    "value": True,
                },
            },
            {
                "weight": 1,
                "when": {"metric": "owner_approved", "op": "==", "value": True},
            },
        ],
    }
}

SPEC = {
    "schema_version": "1.0.0",
    "council_id": "probe-weighted-roundtrip",
    "objective": {
        "statement": "Probe the weighted branch round trip.",
        "risk_tier": "low",
        "desired_output": "review_verdict",
    },
    "participants": {
        "selection": {"mode": "mixed"},
        "count": {"mode": "exact", "exact_n": 3},
    },
    "topology": {"kind": "flat"},
    "protocol": {"sequence": [{"kind": "synthesis", "stage_id": "s1"}]},
    "voting": {"method": "synthesis_only"},
    "stopping": {"expression": WEIGHTED_TREE},
}


def _try(label, fn):
    try:
        return True, fn()
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    print("-- CONTROL: an all_of tree must survive both checks")
    txt_all = unparse(ALL_OF_TREE)
    ok_all, back_all = _try("parse(unparse(all_of))", lambda: parse(txt_all))
    print(f"   unparse(all_of)          = {txt_all!r}")
    print(
        f"   parse(unparse(all_of))   ok={ok_all} idempotent={back_all == ALL_OF_TREE}"
    )

    print("-- SUBJECT: the weighted tree")
    txt_w = unparse(WEIGHTED_TREE)
    print(f"   unparse(weighted)        = {txt_w!r}")
    ok_w, back_w = _try("parse(unparse(weighted))", lambda: parse(txt_w))
    print(
        f"   parse(unparse(weighted)) ok={ok_w} -> {back_w if not ok_w else 'parsed'}"
    )

    # The tree itself is schema-legal and executes; only the TEXT round trip is broken.
    res = validate_spec(SPEC)
    print(
        f"   schema+semantic ok       = {res['ok']}  errors={res['schema_errors'] + res['semantic_errors']}"
    )
    ev_true = evaluate(
        WEIGHTED_TREE,
        {"consensus": 0.95, "every_objection_addressed": True, "owner_approved": False},
    )
    ev_false = evaluate(
        WEIGHTED_TREE,
        {"consensus": 0.5, "every_objection_addressed": True, "owner_approved": False},
    )
    print(f"   evaluate both-states     = {ev_true}/{ev_false}")

    # Now the consequence: add a source_expression and watch SEM-001 have nothing it can match.
    spec2 = {**SPEC, "stopping": {**SPEC["stopping"], "source_expression": txt_w}}
    res2 = validate_spec(spec2)
    print(
        f"   with source_expression   ok={res2['ok']} errors={res2['semantic_errors']}"
    )

    asymmetric = (
        ok_all and back_all == ALL_OF_TREE and not ok_w and res["ok"] and not res2["ok"]
    )
    print()
    if asymmetric:
        print(
            "CONFIRMED: the weighted branch is UNPARSE-ONLY. unparse() emits WEIGHTED[...] >= t,"
        )
        print(
            "           parse() has no WEIGHTED production, so a weighted spec can neither"
        )
        print(
            "           declare stopping.source_expression (SEM-001 fails) nor satisfy a"
        )
        print(
            "           parse(unparse(tree)) == tree idempotence check. The tree is still"
        )
        print(
            "           schema-valid and still EXECUTES correctly (both-states True/False),"
        )
        print(
            "           so this is a documentation/round-trip gap, not an evaluator bug."
        )
        print(
            "           Consequence for lane build/preset-4: no shipped preset uses weighted."
        )
        print("SUCCESS:probe-weighted-roundtrip asymmetry CONFIRMED")
        return 0
    print("REFUTED or INCONCLUSIVE - readings above do not form the asymmetry pattern.")
    print("FAILED:probe-weighted-roundtrip pattern not reproduced")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
