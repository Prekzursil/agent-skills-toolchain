"""Generate the invalid CouncilSpec fixtures as SINGLE mutations of the valid ones.

Hand-authoring a negative fixture risks it failing for a reason other than the defect you
meant to test. Deriving each one from a known-PASSING base by exactly one mutation site is
the both-states control: the base validates, the mutant does not, and the only difference is
the named defect.

    python -m councilspec.make_negatives            # write fixtures
    python -m councilspec.make_negatives --check    # verify on-disk fixtures match (no write)
"""

from __future__ import annotations

import argparse
import copy
import json
import os
from typing import Any, Dict, List, NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))
EXAMPLES = os.path.abspath(os.path.join(HERE, "..", "..", "schema", "examples"))
VALID = os.path.join(EXAMPLES, "valid")
INVALID = os.path.join(EXAMPLES, "invalid")

SENTINEL = object()


class Mutation(NamedTuple):
    out: str
    base: str
    path: List[Any]                       # the ONE site that changes
    value: Any                            # SENTINEL means delete the key
    drop_source_expression: bool
    defect: str


def _navigate(doc: Any, path: List[Any]) -> Any:
    node = doc
    for key in path[:-1]:
        node = node[key]
    return node


def apply_mutation(base_doc: Dict[str, Any], mut: Mutation) -> Dict[str, Any]:
    doc = copy.deepcopy(base_doc)
    parent = _navigate(doc, mut.path)
    leaf = mut.path[-1]
    if mut.value is SENTINEL:
        del parent[leaf]
    else:
        parent[leaf] = copy.deepcopy(mut.value)
    if mut.drop_source_expression:
        doc.get("stopping", {}).pop("source_expression", None)
    return doc


MUTATIONS: List[Mutation] = [
    Mutation(
        out="N1-typed-leaf-violation.councilspec.json",
        base="E2-architecture-review-board.councilspec.json",
        path=["stopping", "expression", "all_of", 0],
        value={"metric": "unanimity", "op": ">=", "value": 0.95},
        drop_source_expression=True,
        defect="`unanimity` is a BOOLEAN metric; >= and a numeric value are illegal for it. "
               "This is the headline proof that the leaf is typed, not merely structural.",
    ),
    Mutation(
        out="N2-unknown-metric.councilspec.json",
        base="E1-hundred-idea-brainstorm.councilspec.json",
        path=["stopping", "expression", "all_of", 0, "metric"],
        value="vibes_score",
        drop_source_expression=True,
        defect="`vibes_score` is not in the schema metric registry, and it is not a "
               "custom:<name> extension either.",
    ),
    Mutation(
        out="N3-count-min-gt-max.councilspec.json",
        base="E1-hundred-idea-brainstorm.councilspec.json",
        path=["participants", "count", "min"],
        value=13,
        drop_source_expression=False,
        defect="participants.count.min (13) exceeds max (12). JSON Schema cannot compare two "
               "sibling fields; SEM-002 does.",
    ),
    Mutation(
        out="N4-supermajority-without-threshold.councilspec.json",
        base="E2-architecture-review-board.councilspec.json",
        path=["voting", "supermajority_threshold"],
        value=SENTINEL,
        drop_source_expression=False,
        defect="voting.method == supermajority with no supermajority_threshold: the schema "
               "if/then makes the threshold mandatory for that method.",
    ),
    Mutation(
        out="N5-source-expression-drift.councilspec.json",
        base="E2-architecture-review-board.councilspec.json",
        path=["stopping", "source_expression"],
        value="consensus >= 0.75 AND no_new_objection_rounds >= 2",
        drop_source_expression=False,
        defect="The human string says 0.75 while the structured tree says 0.95. SEM-001 "
               "catches doc/tree drift, the failure mode where the readable form lies.",
    ),
    Mutation(
        out="N6-unknown-top-level-key.councilspec.json",
        base="E3-oxford-debate-unanimity-or-12-rounds.councilspec.json",
        path=["stopping_rules"],
        value={"max_rounds": 12},
        drop_source_expression=False,
        defect="`stopping_rules` is a plausible typo for `stopping`; additionalProperties:false "
               "rejects it instead of silently ignoring a rule the author thought was live.",
    ),
    Mutation(
        out="N7-delegation-cycle.councilspec.json",
        base="E2-architecture-review-board.councilspec.json",
        path=["voting", "delegation"],
        value={
            "allowed": True,
            "max_chain_length": 3,
            "cycles_forbidden": True,
            "map": {"cost-analyst": "migration-lead", "migration-lead": "cost-analyst"},
        },
        drop_source_expression=False,
        defect="Two participants delegate to each other, so the vote never resolves. SEM-008 "
               "walks the chain.",
    ),
    Mutation(
        out="N8-round-cap-incoherence.councilspec.json",
        base="E3-oxford-debate-unanimity-or-12-rounds.councilspec.json",
        path=["stopping", "expression"],
        value={
            "any_of": [
                {"metric": "unanimity", "op": "==", "value": True},
                {"metric": "max_rounds", "op": "==", "value": 20},
            ]
        },
        drop_source_expression=True,
        defect="The rule fires at max_rounds == 20 while the configured caps are 12, so the "
               "second disjunct is unreachable. SEM-011 refuses the dead clause.",
    ),
    Mutation(
        out="N9-council-of-councils-without-subcouncils.councilspec.json",
        base="E6-council-of-councils-impossibility.councilspec.json",
        path=["topology", "subcouncils"],
        value=SENTINEL,
        drop_source_expression=False,
        defect="topology.kind == council_of_councils with no subcouncils: the schema if/then "
               "requires them.",
    ),
    Mutation(
        out="N10-idea-gate-without-brainstorm.councilspec.json",
        base="E1-hundred-idea-brainstorm.councilspec.json",
        path=["protocol", "sequence"],
        value=[
            {"kind": "round_robin", "stage_id": "talk", "rounds": 3},
            {"kind": "synthesis", "stage_id": "close"},
        ],
        drop_source_expression=False,
        defect="The rule gates on unique_ideas >= 100 but no stage generates ideas, so the "
               "council can never stop. SEM-007 catches the unreachable target.",
    ),
]


def build() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for mut in MUTATIONS:
        with open(os.path.join(VALID, mut.base), "r", encoding="utf-8") as fh:
            base_doc = json.load(fh)
        out[mut.out] = apply_mutation(base_doc, mut)
    return out


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="councilspec.make_negatives")
    ap.add_argument("--check", action="store_true", help="verify without writing")
    args = ap.parse_args(argv)

    os.makedirs(INVALID, exist_ok=True)
    built = build()
    drift = []
    for name, doc in built.items():
        path = os.path.join(INVALID, name)
        text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
        if args.check:
            if not os.path.isfile(path):
                drift.append(f"missing {name}")
                continue
            with open(path, "r", encoding="utf-8") as fh:
                if json.load(fh) != doc:
                    drift.append(f"content drift in {name}")
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)
            print(f"wrote {name}")

    if args.check:
        if drift:
            print("\n".join(drift))
            print("FAILED:councilspec-negatives fixtures do not match the declared mutations")
            return 1
        print(f"-- {len(built)} generated fixtures match their declared single mutation")
        print("SUCCESS:councilspec-negatives")
        return 0
    print(f"-- {len(built)} fixtures written to {INVALID}")
    print("SUCCESS:councilspec-negatives")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
