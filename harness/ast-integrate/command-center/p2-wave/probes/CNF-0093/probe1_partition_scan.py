#!/usr/bin/env python3
"""Probe 1: hunt the partitioned canary (verbatim + paraphrase) in non-owning streams.

Holding fixture must be silent. Planted leaks on transcript, synthesis (laundered
paraphrase), and tool results must fire. A redaction-disabled fixture must fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detector as D  # noqa: E402
import partition_runtime as PR  # noqa: E402
import scenario as S  # noqa: E402
from canaries import PARTITION_CANARY  # noqa: E402

OUT = HERE / "probe1-partition-scan.raw.json"


def _hits_for(run: dict, needle: str, paraphrase: bool) -> list[dict]:
    streams = PR.non_owning_streams(run)
    return D.search_streams(streams, needle, paraphrase=paraphrase)


def _count(rows: list[dict], kind_prefix: str | None = None) -> int:
    n = 0
    for row in rows:
        for hit in row.get("hits") or []:
            if kind_prefix is None or str(hit.get("kind") or "").startswith(kind_prefix):
                n += 1
    return n


def main() -> int:
    if not D.is_benign_token(PARTITION_CANARY):
        print("FAILED:CNF-0093-probe1 canary is not a benign synthetic token")
        return 1
    assembled = S.build_fixtures()
    holding = assembled["holding"]
    owner_rows = D.search_streams(
        PR.owning_streams(holding), PARTITION_CANARY, paraphrase=False
    )
    if not D.any_hits(owner_rows):
        print("FAILED:CNF-0093-probe1 partitioned canary missing from owning seat")
        return 1

    hold_rows = _hits_for(holding, PARTITION_CANARY, paraphrase=True)
    tx_rows = _hits_for(
        assembled["leak-shared-transcript"], PARTITION_CANARY, paraphrase=True
    )
    syn_rows = _hits_for(
        assembled["leak-synthesis-paraphrase"], PARTITION_CANARY, paraphrase=True
    )
    tool_rows = _hits_for(
        assembled["leak-tool-results"], PARTITION_CANARY, paraphrase=True
    )
    off_rows = _hits_for(
        assembled["redaction-disabled"], PARTITION_CANARY, paraphrase=True
    )

    hold_n = _count(hold_rows)
    tx_verb = _count(tx_rows, "verbatim")
    syn_para = _count(syn_rows, "paraphrase")
    tool_verb = _count(tool_rows, "verbatim")
    off_n = _count(off_rows)

    live = PR.live_partition_module(REPO)
    payload = {
        "probe": "probe1-partition-scan",
        "unit_id": "CNF-0093",
        "holding_non_owning_hits": hold_n,
        "leak_transcript_verbatim_hits": tx_verb,
        "leak_synthesis_paraphrase_hits": syn_para,
        "leak_tool_verbatim_hits": tool_verb,
        "redaction_disabled_hits": off_n,
        "owning_seat_has_canary": True,
        "live_partition_module": live,
        "canary_benign": True,
        "pass": False,
    }

    if hold_n != 0:
        payload["error"] = "holding fixture leaked partitioned canary"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe1 holding leak")
        return 1
    if tx_verb < 1:
        payload["error"] = "transcript planted leak did not fire verbatim"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe1 transcript detector silent")
        return 1
    if syn_para < 1:
        payload["error"] = "synthesis laundered leak did not fire paraphrase"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe1 paraphrase detector silent")
        return 1
    if tool_verb < 1:
        payload["error"] = "tool-result planted leak did not fire verbatim"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe1 tool-result detector silent")
        return 1
    if off_n < 1:
        payload["error"] = "redaction-disabled negative control did not fire"
        OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(json.dumps(payload, sort_keys=True))
        print("FAILED:CNF-0093-probe1 redaction-disabled silent")
        return 1

    payload["pass"] = True
    payload["holding_rows"] = hold_rows
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "holding_hits="
        + str(hold_n)
        + " transcript_verbatim="
        + str(tx_verb)
        + " synthesis_paraphrase="
        + str(syn_para)
        + " tool_verbatim="
        + str(tool_verb)
        + " redaction_disabled="
        + str(off_n)
        + " live_partition_present="
        + str(live["present"])
    )
    print("SUCCESS:CNF-0093-probe1 partition scan verbatim+paraphrase")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
