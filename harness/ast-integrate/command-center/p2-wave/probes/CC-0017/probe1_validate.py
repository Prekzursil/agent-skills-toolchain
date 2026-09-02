#!/usr/bin/env python3
"""Named probe 1: schema semantic tests (settling probe, duplicate-of cycle, dangling contradiction).

Mechanically different from probe 2 (which re-runs migration + schedule).
Both-states: a complete record is accepted; each mutant is rejected.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import validate as V  # noqa: E402

MECH = "A named settling probe is mandatory on every canonical claim record."


def _print(ok: bool, label: str, detail: str) -> None:
    print(f"{'PASS' if ok else 'FAIL'} {label} {detail}")


def main() -> int:
    ok_prov, why_prov = V.schema_is_provisional()
    _print(ok_prov, "schema-provisional", why_prov)
    if not ok_prov:
        print("FAILED:CC-0017-probe1 schema is not marked PROVISIONAL/ARC-0085")
        return 1

    good = V.fixture_record("CR-GOOD-SETTLE", MECH)
    good_peer = V.fixture_record(
        "CR-GOOD-PEER",
        "Peer record exists so contradiction targets can resolve.",
    )
    good_errs = V.validate_record(good)
    _print(not good_errs, "good-record", str(good_errs[:3]))
    if good_errs:
        print("FAILED:CC-0017-probe1 good record rejected")
        return 1

    missing = copy.deepcopy(good)
    del missing["settling_probe"]
    miss_errs = V.validate_record(missing)
    miss_ok = any("settling" in e.lower() or "required" in e.lower() for e in miss_errs)
    _print(miss_ok, "no-settling-probe-rejected", str(miss_errs[:4]))
    if not miss_ok:
        print("FAILED:CC-0017-probe1 missing settling_probe was accepted")
        return 1

    empty = copy.deepcopy(good)
    empty["settling_probe"] = {"id": "", "command": ""}
    empty_errs = V.validate_record(empty)
    empty_ok = bool(empty_errs)
    _print(empty_ok, "empty-settling-probe-rejected", str(empty_errs[:4]))
    if not empty_ok:
        print("FAILED:CC-0017-probe1 empty settling_probe was accepted")
        return 1

    a = V.fixture_record(
        "CR-CYCLE-A",
        "Duplicate-of cycle left side of a two-node loop.",
        duplicate_of=["CR-CYCLE-B"],
    )
    b = V.fixture_record(
        "CR-CYCLE-B",
        "Duplicate-of cycle right side of a two-node loop.",
        duplicate_of=["CR-CYCLE-A"],
    )
    cycle_errs = V.validate_record_set([a, b])
    cycle_ok = any("duplicate_of-cycle" in e for e in cycle_errs)
    _print(cycle_ok, "duplicate-of-cycle-rejected", str(cycle_errs[:4]))
    if not cycle_ok:
        print("FAILED:CC-0017-probe1 duplicate-of cycle was accepted")
        return 1

    acyclic = V.validate_record_set(
        [
            V.fixture_record(
                "CR-ACYC-A",
                "Acyclic duplicate-of edge pointing at a live peer.",
                duplicate_of=["CR-ACYC-B"],
            ),
            V.fixture_record(
                "CR-ACYC-B",
                "Acyclic duplicate-of sink with no back edge.",
            ),
        ]
    )
    acyc_ok = acyclic == []
    _print(acyc_ok, "acyclic-duplicate-accepted", str(acyclic[:3]))
    if not acyc_ok:
        print("FAILED:CC-0017-probe1 acyclic duplicate-of was rejected")
        return 1

    dangling = V.fixture_record(
        "CR-CONTRA-SRC",
        "Contradiction edge aimed at an id that is not in the set.",
        contradiction=["CR-DOES-NOT-EXIST"],
    )
    dang_errs = V.validate_record_set([dangling, good_peer])
    dang_ok = any("nonexistent" in e for e in dang_errs)
    _print(dang_ok, "dangling-contradiction-rejected", str(dang_errs[:4]))
    if not dang_ok:
        print("FAILED:CC-0017-probe1 dangling contradiction was accepted")
        return 1

    live = V.fixture_record(
        "CR-CONTRA-SRC-OK",
        "Contradiction edge aimed at a claim id that exists.",
        contradiction=["CR-GOOD-PEER"],
    )
    live_errs = V.validate_record_set([live, good_peer])
    live_ok = live_errs == []
    _print(live_ok, "live-contradiction-accepted", str(live_errs[:3]))
    if not live_ok:
        print("FAILED:CC-0017-probe1 live contradiction target was rejected")
        return 1

    if not (
        miss_ok
        and empty_ok
        and cycle_ok
        and dang_ok
        and (not good_errs)
        and acyc_ok
        and live_ok
    ):
        print("FAILED:CC-0017-probe1 both-states did not discriminate")
        return 1
    print(
        "fired_on_bad=True silent_on_good=True "
        "settling=True cycle=True dangling_contradiction=True"
    )
    print("SUCCESS:CC-0017-probe1 settling-probe cycle contradiction both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
