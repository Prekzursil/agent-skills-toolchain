#!/usr/bin/env python3
"""Probe 2: both-states + adversarial fifth mutation (mechanically different).

Does not consume the harness summary table. Applies each mutator on a fresh
copy, requires:
  * identity / clean GREEN
  * each of the four contracted mutations RED, with distinct failure-id prefixes
  * control RED
  * fifth (catchall trigger) RED
  * no leakage: a final clean re-run stays GREEN
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    CONTRACTED,
    CONTROL,
    FIFTH,
    IDENTITY,
    _run_one,
)
from router import load_config  # noqa: E402
from suite import run_suite  # noqa: E402


def _prefixes(failure_ids: list[str]) -> set[str]:
    out: set[str] = set()
    for fid in failure_ids:
        out.add(str(fid).split(":", 1)[0])
    return out


def main() -> int:
    base = load_config()
    clean = run_suite(base)
    if not clean["green"]:
        print(f"FAILED:IMP-0399-probe2 clean RED {clean['failures'][:6]}")
        return 1

    ident = _run_one(*IDENTITY, base)
    if ident["observed"] != "GREEN":
        print("FAILED:IMP-0399-probe2 identity not GREEN — always-red detector")
        return 1

    prefix_sets: dict[str, set[str]] = {}
    for name, mut in CONTRACTED:
        row = _run_one(name, mut, base)
        if row["observed"] != "RED":
            print(f"FAILED:IMP-0399-probe2 {name} stayed GREEN")
            return 1
        prefs = _prefixes(row["failure_ids"])
        if not prefs:
            print(f"FAILED:IMP-0399-probe2 {name} RED but no failure ids")
            return 1
        prefix_sets[name] = prefs

    # Distinct detection: unpin must cite PIN-*; invert must cite BAN-LEAK or
    # CORPUS on the ban query; delete-trigger must cite CORPUS on cwd queries.
    unpin_prefs = prefix_sets["unpin_embedding"]
    if "PIN-REQUIRED" not in unpin_prefs and "PIN-DIGEST" not in unpin_prefs:
        print(f"FAILED:IMP-0399-probe2 unpin did not fail a PIN-* check: {unpin_prefs}")
        return 1
    inv_ids = " ".join(
        _run_one("invert_precedence", dict(CONTRACTED)["invert_precedence"], base)[
            "failure_ids"
        ]
    )
    if "q-ban-dump" not in inv_ids and "BAN-LEAK" not in inv_ids:
        print(f"FAILED:IMP-0399-probe2 invert did not expose ban leak: {inv_ids}")
        return 1
    del_ids = " ".join(
        _run_one("delete_trigger_row", dict(CONTRACTED)["delete_trigger_row"], base)[
            "failure_ids"
        ]
    )
    if "q-secret-cwd" not in del_ids:
        print(f"FAILED:IMP-0399-probe2 delete-trigger missed cwd queries: {del_ids}")
        return 1
    cor_ids = " ".join(
        _run_one("corrupt_description", dict(CONTRACTED)["corrupt_description"], base)[
            "failure_ids"
        ]
    )
    if "q-ledger-para" not in cor_ids:
        print(f"FAILED:IMP-0399-probe2 corrupt-description missed paraphrase: {cor_ids}")
        return 1

    control = _run_one(*CONTROL, base)
    if control["observed"] != "RED":
        print("FAILED:IMP-0399-probe2 control stayed GREEN — cannot observe redness")
        return 1
    fifth = _run_one(*FIFTH, base)
    if fifth["observed"] != "RED":
        print("FAILED:IMP-0399-probe2 fifth mutation survived")
        return 1

    again = run_suite(load_config())
    if not again["green"]:
        print("FAILED:IMP-0399-probe2 leaked mutation into clean config")
        return 1

    print(
        "clean=GREEN identity=GREEN contracted=4/4 RED "
        f"control={control['observed']} fifth={fifth['observed']} "
        f"unpin_prefixes={sorted(unpin_prefs)}"
    )
    print("SUCCESS:IMP-0399-probe2 both-states and fifth mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
