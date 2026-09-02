#!/usr/bin/env python3
"""Probe 2: negative control + independent trigram recount of both-states.

Negative control (verbatim):
  - SATURATION-stop on the padding fixture is SILENT (stop_round is false).
  - QUOTA_FILLING fire on the saturated fixture is SILENT (decision is SATURATION).

The independent reviewer path re-derives unique yield with char-trigrams
(not token Jaccard) and must reach the same decision on both fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0055-saturation-versus-quota-filling-at-the-100-idea-target.md"
)


def _run(name: str) -> dict:
    pack = F.build(name)
    return D.classify_both(pack["ledger"], pack["offered"], quota=pack["quota"])


def main() -> int:
    padding = _run("padding")
    saturated = _run("saturated")
    early = _run("early_saturation")
    cont = _run("continue")

    sat_stop_on_padding = padding["stop_round"]
    pad_fire_on_saturated = saturated["decision"] == "QUOTA_FILLING"
    print(
        "negative_control_saturation_stop_on_padding="
        f"{'FIRES' if sat_stop_on_padding else 'SILENT'}"
    )
    print(
        "negative_control_quota_filling_on_saturated="
        f"{'FIRES' if pad_fire_on_saturated else 'SILENT'}"
    )
    print(
        "independent_trigram_padding="
        f"{padding['independent_trigram']['decision']} "
        f"yield={padding['independent_trigram']['unique_yield']}"
    )
    print(
        "independent_trigram_saturated="
        f"{saturated['independent_trigram']['decision']} "
        f"yield={saturated['independent_trigram']['unique_yield']}"
    )
    print(
        "signal2_padding_volume_chases="
        f"{padding['signal2_raw_volume']['volume_chases_quota']} "
        f"offered={padding['signal2_raw_volume']['offered_n']} "
        f"raw_gap={padding['signal2_raw_volume']['raw_gap']}"
    )
    print(
        "signal2_saturated_volume_chases="
        f"{saturated['signal2_raw_volume']['volume_chases_quota']} "
        f"offered={saturated['signal2_raw_volume']['offered_n']} "
        f"raw_gap={saturated['signal2_raw_volume']['raw_gap']}"
    )
    print(
        f"continue_decision={cont['decision']} "
        f"early_saturation_stop={early['stop_round']} "
        f"early_satisfy_quota={early['satisfy_unique_quota']}"
    )

    if sat_stop_on_padding:
        print("FAILED:CNL-0055-probe2 saturation-stop fired on padding (meant to reject this)")
        return 1
    if pad_fire_on_saturated:
        print("FAILED:CNL-0055-probe2 quota-filling fired on saturated (meant to reject this)")
        return 1
    if padding["independent_trigram"]["decision"] != "QUOTA_FILLING":
        print("FAILED:CNL-0055-probe2 independent trigram missed padding")
        return 1
    if saturated["independent_trigram"]["decision"] != "SATURATION":
        print("FAILED:CNL-0055-probe2 independent trigram missed saturation")
        return 1
    if padding["independent_trigram"]["unique_yield"] != 0:
        print("FAILED:CNL-0055-probe2 independent trigram unique_yield on padding")
        return 1
    if saturated["independent_trigram"]["unique_yield"] != 0:
        print("FAILED:CNL-0055-probe2 independent trigram unique_yield on saturated")
        return 1
    if padding["signal2_raw_volume"]["volume_chases_quota"] is not True:
        print("FAILED:CNL-0055-probe2 signal2 volume chase silent on padding")
        return 1
    if saturated["signal2_raw_volume"]["volume_chases_quota"] is not False:
        print("FAILED:CNL-0055-probe2 signal2 volume chase fired on saturated")
        return 1
    if cont["decision"] != "CONTINUE":
        print("FAILED:CNL-0055-probe2 continue fixture misclassified")
        return 1
    if early["stop_round"] is not True or early["satisfy_unique_quota"] is not False:
        print("FAILED:CNL-0055-probe2 early saturation must stop without satisfying quota")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0055-probe2 design note missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    negs = doc.get("negative_controls") or []
    observed = {n.get("id"): n.get("observed") for n in negs if isinstance(n, dict)}
    if observed.get("saturation-stop-on-padding") != "SILENT":
        print("FAILED:CNL-0055-probe2 artifact negative control padding drift")
        return 1
    if observed.get("quota-filling-on-saturated") != "SILENT":
        print("FAILED:CNL-0055-probe2 artifact negative control saturated drift")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("re_ran_both_states") is not True or reviewer.get("independent") is not True:
        print("FAILED:CNL-0055-probe2 reviewer did not re-run both-states")
        return 1
    print("SUCCESS:CNL-0055-probe2 negative-control independent-recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
