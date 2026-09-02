#!/usr/bin/env python3
"""Probe 1: de-anonymisation attempt on a pseudonymous transcript + vote history.

The adversary receives the publishable log and the invite list, not the keeper
binder or round salts. A known-good fixture must yield zero confident joins.
Planted-bad fixtures (name in dissent, embedded binder, unshuffled order) must
be re-identified. Chance baseline is 1/n.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import anonymity as A  # noqa: E402

OUT = HERE / "probe1-deanonymisation.raw.json"


def main() -> int:
    A.dump_fixtures()
    states = A.deanonymisation_states()
    good = states["good_pseudonymous"]
    OUT.write_text(json.dumps(states, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "good_pseudonymous "
        f"chance={good['chance_baseline']} "
        f"confident_joins={good['confident_join_count']} "
        f"confident_accuracy={good['confident_accuracy']} "
        f"forced_position_accuracy={good['forced_position_accuracy']} "
        f"supports_anonymity={good['supports_anonymity']}"
    )
    bad_n = states["bad_name_in_dissent"]
    print(
        "bad_name_in_dissent "
        f"confident_joins={bad_n['confident_join_count']} "
        f"confident_accuracy={bad_n['confident_accuracy']} "
        f"supports_anonymity={bad_n['supports_anonymity']}"
    )
    bad_b = states["bad_binder_embedded"]
    print(
        "bad_binder_embedded "
        f"confident_joins={bad_b['confident_join_count']} "
        f"supports_anonymity={bad_b['supports_anonymity']}"
    )
    bad_o = states["bad_unshuffled_order"]
    print(
        "bad_unshuffled_order "
        f"forced_position_accuracy={bad_o['forced_position_accuracy']} "
        f"supports_anonymity={bad_o['supports_anonymity']}"
    )
    print(
        "negative_control: on planted-bad name-in-dissent the attack produces "
        f"{bad_n['confident_join_count']} confident join(s) "
        f"(accuracy={bad_n['confident_accuracy']}); that is the reject state."
    )
    if not states["pass"]:
        print("FAILED:CNL-0007-probe1 de-anonymisation did not discriminate")
        return 1
    print("SUCCESS:CNL-0007-probe1 de-anonymisation attempt recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
