#!/usr/bin/env python3
"""Probe 1: computed evidence-class coverage == 100%, both-states.

Live harvest of all four blueprints is scored (tagged/total). A planted
untagged claim must drop coverage. Niche-forum must emit practitioner_anecdote
as a distinct class from documentation; collapsing the two must fail the
split check. Six one-at-a-time contract omissions must produce six distinct
rejection tokens. A forums-denied policy must refuse niche-forum rather than
silently skip it.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from blueprints import library  # noqa: E402
from claims import evidence_class_coverage, forum_class_split  # noqa: E402
from contract import REQUIRED_ELEMENTS, omission_failures  # noqa: E402
from engine import HarvestError, run_library  # noqa: E402
from policy import SourcePolicyError, default_policy, enforce  # noqa: E402
from taxonomy import anecdote_is_distinct_from_documentation  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:IMP-0236-probe1 {msg}")
    return 1


def main() -> int:
    lib = library()
    if set(lib) != {
        "prior-art-patent",
        "standards-regulatory",
        "niche-forum",
        "multilingual",
    }:
        return _fail(f"unexpected blueprint ids {sorted(lib)}")

    harvest = run_library(lib)
    cov = harvest["coverage"]
    print(
        "live_coverage="
        f"{cov['coverage']} tagged={cov['tagged']} total={cov['total']} "
        f"untagged={cov['untagged']}"
    )
    if cov["total"] < 8:
        return _fail(f"harvest too small to be a coverage test: total={cov['total']}")
    if cov["coverage"] != 1.0 or cov["untagged"] != 0:
        return _fail(f"live coverage is not 100%: {cov}")

    planted = list(harvest["claims"])
    planted.append(
        {
            "id": "plant-untagged",
            "text": "a statement with the evidence_class field omitted",
            "source_id": "plant",
            "blueprint_id": "niche-forum",
        }
    )
    planted_cov = evidence_class_coverage(planted)
    print(
        "planted_untagged_coverage="
        f"{planted_cov['coverage']} untagged_ids={planted_cov['untagged_ids']}"
    )
    if planted_cov["coverage"] >= 1.0:
        return _fail("coverage scorer stayed at 1.0 after an untagged plant")
    if "plant-untagged" not in planted_cov["untagged_ids"]:
        return _fail("coverage scorer did not name the planted untagged claim")

    split = harvest["forum_split"]
    print(
        "forum_split "
        f"anecdote={split['anecdote_count']} docs={split['documentation_count']} "
        f"split_ok={split['split_ok']} classes_distinct={split['classes_distinct']}"
    )
    if not anecdote_is_distinct_from_documentation():
        return _fail("practitioner_anecdote is not a distinct evidence-class token")
    if not split["split_ok"]:
        return _fail("niche-forum did not emit both anecdote and documentation")

    collapsed = copy.deepcopy(
        [c for c in harvest["claims"] if c.get("blueprint_id") == "niche-forum"]
    )
    for claim in collapsed:
        if claim.get("evidence_class") == "practitioner_anecdote":
            claim["evidence_class"] = "documentation"
    collapsed_split = forum_class_split(collapsed)
    print(f"collapsed_anecdote_to_docs split_ok={collapsed_split['split_ok']}")
    if collapsed_split["split_ok"]:
        return _fail("collapsing anecdote into documentation still passed split_ok")

    tokens: list[str] = []
    sample = next(iter(lib.values()))
    for element in REQUIRED_ELEMENTS:
        mutant = dict(sample)
        mutant.pop(element, None)
        fails = omission_failures(mutant)
        print(f"omission[{element}] -> {fails}")
        if fails != [f"missing:{element}"]:
            return _fail(f"omission {element} did not produce a distinct token")
        tokens.append(fails[0])
    if len(set(tokens)) != 6:
        return _fail(f"omission tokens not distinct: {tokens}")

    denied = default_policy()
    denied["allowed"] = [c for c in denied["allowed"] if c != "forums"]
    try:
        enforce("niche-forum", denied)
        return _fail("forums-denied policy did not refuse niche-forum")
    except SourcePolicyError as exc:
        print(f"forums_denied_refused={exc}")

    tor = default_policy()
    tor["allowed"] = list(tor["allowed"]) + ["public-tor"]
    tor["owner_tor_flag"] = False
    try:
        enforce("niche-forum", tor)
        return _fail("tor class without owner flag did not refuse")
    except SourcePolicyError as exc:
        print(f"tor_without_flag_refused={exc}")

    print(
        json.dumps(
            {
                "coverage": cov,
                "forum_split": split,
                "omission_tokens": tokens,
                "planted_coverage": planted_cov["coverage"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0236-probe1 evidence-class coverage 100% both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
