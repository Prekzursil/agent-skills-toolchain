#!/usr/bin/env python3
"""Probe 2: planted-mutation both-states control plus undeclared-loss detector."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import evaluate_all  # noqa: E402


def main() -> int:
    report = evaluate_all()
    failures: list[str] = []
    for row in report["planted_mutation"]:
        print(
            f"adapter={row['adapter_id']} item={row['corpus_id']} "
            f"plant={row['plant_path']} clean={row['clean_admitted']} "
            f"caught={row['planted_caught']} both_states={row['both_states_ok']}"
        )
        if not row["both_states_ok"]:
            failures.append(
                f"{row['adapter_id']}: clean={row['clean_admitted']} "
                f"caught={row['planted_caught']} differing={row['planted_differing']}"
            )
    drop = report["silent_drop_control"]
    print(
        f"silent_drop caught={drop['caught']} dropped={drop['dropped']} "
        f"undeclared={drop['undeclared_losses']}"
    )
    if not drop["caught"]:
        failures.append("silent-drop control was not caught")
    if drop.get("in_ledger"):
        failures.append("silent-drop path was listed as lossy; control is vacuous")
    anchor = report["missing_anchor_control"]
    print(f"missing_anchor raised={anchor['raised']} message={anchor['message']}")
    if not anchor["raised"]:
        failures.append("IR node missing source_anchor was accepted")
    if not report["planted_all_caught"]:
        failures.append("not every adapter planted mutation was caught")
    if failures:
        print("FAILED:WFA-0054-probe2 " + " | ".join(failures))
        return 1
    print(
        "both_states=clean-admitted+planted-caught "
        "silent_drop_caught=True missing_anchor_rejected=True"
    )
    print("SUCCESS:WFA-0054-probe2 planted-mutation both-states control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
