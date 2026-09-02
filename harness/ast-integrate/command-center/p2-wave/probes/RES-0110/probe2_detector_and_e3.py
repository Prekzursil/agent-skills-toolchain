#!/usr/bin/env python3
"""Probe 2: detector both-states, E3 cannot promote, omitted search cannot promote."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import (  # noqa: E402
    OUTPUT_REL,
    REPO,
    SCHEMA_REL,
    SENTINEL,
    UNIT_ID,
)
from promote import promote_row  # noqa: E402
from search import detector_control, load_index, search_mechanism  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    path = REPO / OUTPUT_REL
    if not path.is_file() or path.stat().st_size <= 0:
        return fail("artifact missing")
    text = path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    validator.validate(doc)
    rejected = 0
    for g in GARBAGE:
        if list(validator.iter_errors(g)):
            rejected += 1
    if rejected != 3:
        return fail(f"schema vacuous garbage_rejected={rejected}")
    print(f"schema_garbage_rejected={rejected}")

    idx = load_index()
    det = detector_control(idx)
    if not det["found_known"]:
        return fail("known-present control not found (silent in the present state)")
    if not det["silent_on_absent"]:
        return fail("planted-absent produced a hit (false positive)")
    if not det["passed"]:
        return fail("detector did not pass both states")
    print(
        f"both_states present_found={det['found_known']} "
        f"absent_silent={det['silent_on_absent']}"
    )

    rows = list((doc.get("register") or {}).get("rows") or [])
    gems = [r for r in rows if (r.get("promotion") or {}).get("is_gem")]
    e3 = [r for r in rows if (r.get("promotion") or {}).get("status") == "E3-NOT-PROMOTED"]
    if not gems:
        return fail("no gems to mutate")
    if not e3:
        return fail("artifact has no E3-NOT-PROMOTED row")
    if any((r.get("promotion") or {}).get("is_gem") for r in e3):
        return fail("E3 row promoted")

    victim = copy.deepcopy(gems[0])
    mech = {
        "id": victim["id"],
        "title": victim["title"],
        "role": "candidate",
        "implementable": True,
        "paper": copy.deepcopy(victim.get("paper") or {}),
    }
    live = search_mechanism(victim["id"], idx)
    good = promote_row(mech, live)
    if not good["is_gem"]:
        return fail(f"live promote of {victim['id']} is not a gem {good}")
    print(f"good_state gem={victim['id']} silent_blockers={good['blockers']}")

    omitted = dict(live)
    omitted["performed"] = False
    omitted["queries"] = []
    omitted["verdict"] = "search-not-performed"
    bad_search = promote_row(mech, omitted)
    if bad_search["is_gem"]:
        return fail("omitted search still promoted")
    if "implementation-search-not-performed" not in bad_search["blockers"]:
        return fail(f"omitted-search blockers {bad_search['blockers']}")
    print(f"omitted_search fired blockers={bad_search['blockers']}")

    stripped = copy.deepcopy(mech)
    stripped["paper"]["effect_size"] = None
    stripped["paper"]["baseline"] = None
    bad_e3 = promote_row(stripped, live)
    if bad_e3["is_gem"]:
        return fail("headline-without-baseline still promoted")
    if bad_e3["evidence_tier"] != "E3":
        return fail(f"expected E3 got {bad_e3['evidence_tier']}")
    print(f"e3_mutant fired tier={bad_e3['evidence_tier']} blockers={bad_e3['blockers']}")

    reviewers = doc.get("reviewers") or []
    if len(reviewers) < 2:
        return fail("need two partitioned reviewers")
    parts = [set(r.get("partition") or []) for r in reviewers]
    if not all(p for p in parts):
        return fail("empty reviewer partition")
    if parts[0] & parts[1]:
        return fail(f"reviewer partitions overlap {parts[0] & parts[1]}")
    if not all(r.get("independent") is True for r in reviewers):
        return fail("reviewer not independent")
    print(f"partitions_disjoint a={sorted(parts[0])} b={sorted(parts[1])}")
    print(f"SUCCESS:{UNIT_ID}-probe2 detector-both-states e3-and-omitted-search")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
