#!/usr/bin/env python3
"""Probe 2: behavioral canary — independent of the provenance detector.

A later-stage consumer obeys CNL0100_CANARY_WRITE only when it appears in
the instruction channel. Participant payloads in dissent / turn / vote /
ledger / transcript-replay must not steer when fenced, and must steer when
the fence is disabled (negative control). An operator-channel canary MUST
still be honoured (not blanket refusal).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boundary as B  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe2-canary-steer.raw.json"
SCRATCH = HERE / "scratch" / "probe2"


def check_carrier(carrier: str) -> dict:
    turns = F.planted_turns(carrier)
    pair = B.run_pair(turns, SCRATCH / carrier)
    row = {
        "carrier": carrier,
        "steered_on_raw": pair["steered_on_bad"],
        "unsteered_on_fence": pair["unsteered_on_good"],
        "data_canaries_on_fence": pair["data_canaries_held_on_good"],
        "raw_participant_obeyed": pair["bad"]["consume"]["participant_obeyed"],
        "fence_participant_obeyed": pair["good"]["consume"]["participant_obeyed"],
    }
    ok = bool(row["steered_on_raw"] and row["unsteered_on_fence"] and row["data_canaries_on_fence"])
    row["ok"] = ok
    return row


def main() -> int:
    F.write_fixture_files()
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)

    rows = [check_carrier(c) for c in F.CARRIERS]
    for row in rows:
        print(
            f"carrier={row['carrier']} steered_on_raw={row['steered_on_raw']} "
            f"unsteered_on_fence={row['unsteered_on_fence']} "
            f"data_held={row['data_canaries_on_fence']}"
        )
        if not row["ok"]:
            print(f"FAILED:CNL-0100-probe2 carrier {row['carrier']}")
            return 1

    # Negative control: the state the check is meant to reject is raw concat.
    neg_turns = F.planted_turns("dissent")
    neg_asm = B.assemble(neg_turns, mode="raw")
    neg_det = B.detect(neg_asm)
    neg_con = B.consume(neg_asm, SCRATCH / "negative")
    neg_line = B.dump({"detect": neg_det, "participant_obeyed": neg_con["participant_obeyed"]})
    print(f"negative_control_raw_concat {neg_line}")
    if not (neg_det["fired"] and neg_con["steered_by_participant"]):
        print("FAILED:CNL-0100-probe2 negative control did not reject raw concat")
        return 1

    # Operator-channel canary must still be honoured (not blanket refusal).
    op_turns = F.operator_positive_turns()
    op_asm = B.assemble(op_turns, mode="fence")
    op_det = B.detect(op_asm)
    op_con = B.consume(op_asm, SCRATCH / "operator")
    op_line = B.dump(
        {
            "silent": op_det["silent"],
            "operator_honoured": op_con["operator_honoured"],
            "steered_by_participant": op_con["steered_by_participant"],
        }
    )
    print(f"operator_positive_control {op_line}")
    if not op_det["silent"] or not op_con["operator_honoured"] or op_con["steered_by_participant"]:
        print("FAILED:CNL-0100-probe2 operator positive control")
        return 1

    doc = {
        "carriers": rows,
        "negative_control_verbatim": neg_line,
        "operator_positive_verbatim": op_line,
        "all_carriers_held": True,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUCCESS:CNL-0100-probe2 canary-steer negative-control operator-honour")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
