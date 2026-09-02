#!/usr/bin/env python3
"""Probe 1: state-machine totality. Independent cartesian product vs DESIGN table.

Catalog tests_required[0]: every (state, event) pair is either defined or
explicitly rejected; no implicit self-loops.

Both-states: dropping one REJECT row from a copy MUST fail totality.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import machine as M  # noqa: E402

DESIGN = REPO / "command-center/phase3/A3/DESIGN.json"
SCHEMA = HERE / "registry.schema.json"


def cartesian() -> list[tuple[str, str]]:
    """Independent enumerator: product of the exported STATES x EVENTS tuples."""
    return [(s, e) for s in M.STATES for e in M.EVENTS]


def main() -> int:
    live = M.full_table()
    live_pairs = {(r["state"], r["event"]) for r in live}
    cart = cartesian()
    cart_set = set(cart)
    print(
        f"cartesian states={len(M.STATES)} events={len(M.EVENTS)} "
        f"pairs={len(cart)} table_rows={len(live)}"
    )
    if len(cart) != len(M.STATES) * len(M.EVENTS):
        print("FAILED:ARC-0017-probe1 cartesian size invariant")
        return 1
    if live_pairs != cart_set or len(live) != len(cart):
        print("FAILED:ARC-0017-probe1 live table != cartesian product")
        return 1
    gaps = M.totality_gaps(live)
    if gaps:
        print(f"FAILED:ARC-0017-probe1 totality gaps {gaps[:12]}")
        return 1
    defined = [r for r in live if r["kind"] == "DEFINED"]
    rejected = [r for r in live if r["kind"] == "REJECT"]
    self_loops = [r for r in defined if r["next"] == r["state"]]
    implicit = [r for r in self_loops if not r["explicit_self_loop"]]
    print(
        f"defined={len(defined)} rejected={len(rejected)} "
        f"explicit_self_loops={len(self_loops)} implicit={len(implicit)}"
    )
    if not defined or not rejected:
        print("FAILED:ARC-0017-probe1 expected both DEFINED and REJECT rows")
        return 1
    if implicit:
        print(f"FAILED:ARC-0017-probe1 implicit self-loops {implicit[:4]}")
        return 1
    if len(self_loops) != 1 or self_loops[0]["event"] != "cache_miss":
        print("FAILED:ARC-0017-probe1 expected exactly one explicit cache_miss self-loop")
        return 1
    for event, tag in (
        ("publish_public", "PR_ONLY_FORBIDS"),
        ("mutate_in_place", "IMMUTABLE_VERSION"),
    ):
        rows = [r for r in rejected if r["event"] == event]
        if len(rows) != len(M.STATES):
            print(f"FAILED:ARC-0017-probe1 {event} not rejected from every state")
            return 1
        if any(tag not in (r["reject_reason"] or "") for r in rows):
            print(f"FAILED:ARC-0017-probe1 {event} missing {tag}")
            return 1

    mutant = copy.deepcopy(live)
    drop = next(r for r in mutant if r["kind"] == "REJECT")
    mutant.remove(drop)
    mutant_gaps = M.totality_gaps(mutant)
    print(
        f"mutant dropped {drop['state']}+{drop['event']} "
        f"gaps={len(mutant_gaps)}"
    )
    if not mutant_gaps:
        print("FAILED:ARC-0017-probe1 mutant still total — detector is a no-op")
        return 1

    if not DESIGN.is_file():
        print("FAILED:ARC-0017-probe1 DESIGN.json absent")
        return 1
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    sm = design.get("state_machine") or {}
    drows = sm.get("table") or []
    if M.table_digest(drows) != M.table_digest(live):
        print("FAILED:ARC-0017-probe1 DESIGN table digest != live machine")
        print(f"  live={M.table_digest(live)}")
        print(f"  design={M.table_digest(drows)}")
        return 1
    if sm.get("pair_count") != len(cart):
        print(f"FAILED:ARC-0017-probe1 DESIGN pair_count {sm.get('pair_count')}")
        return 1
    if "SUCCESS:ARC-0017" not in json.dumps(design):
        print("FAILED:ARC-0017-probe1 sentinel absent from DESIGN")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    pkg = M.paper_package_skill_council()
    import jsonschema

    jsonschema.Draft7Validator(schema).validate(pkg["index"])
    lock_schema = {
        "$ref": "#/definitions/lockfile",
        "definitions": schema["definitions"],
    }
    jsonschema.Draft7Validator(lock_schema).validate(pkg["lockfile"])
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not list(jsonschema.Draft7Validator(schema).iter_errors(garbage)):
        print("FAILED:ARC-0017-probe1 registry schema accepted garbage")
        return 1
    print(
        f"paper package id={pkg['release']['package_id']} "
        f"digest={pkg['payload_sha256'][:12]} "
        f"walk_terminal={pkg['terminal_state']} "
        f"not_claimed={len(pkg['not_claimed_sibling_ids'])}"
    )
    if pkg["terminal_state"] != "INSTALLED":
        print("FAILED:ARC-0017-probe1 paper install walk did not reach INSTALLED")
        return 1
    print("SUCCESS:ARC-0017-probe1 state-machine totality")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
