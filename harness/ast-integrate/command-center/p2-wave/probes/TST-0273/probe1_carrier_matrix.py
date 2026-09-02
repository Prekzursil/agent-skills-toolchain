#!/usr/bin/env python3
"""Probe 1: carrier matrix — each participant artifact is isolated and reported.

For every named carrier (position paper, transcript, idea ledger, evidence
bundle, tool result, display name) plant a unique EXECUTE_CANARY payload,
assemble with the defended runtime, and require:

  * the later stage does not obey
  * the canary token still reaches the assembled DATA (not dropped)
  * the live directive was neutralized in that carrier

A clean round must stay silent. Dropping the payload instead of fencing it
must fail the reachability check (detector control).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

from scenario import CARRIERS, UNIT, run_carrier_matrix  # noqa: E402

ART = REPO / "command-center/receipts/TST-0273.json"


def check_artifact_if_present() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0273" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    return None


def fail(msg: str) -> int:
    print(f"FAILED:TST-0273-probe1 {msg}")
    return 1


def main() -> int:
    art_err = check_artifact_if_present()
    if art_err:
        return fail(art_err)

    result = run_carrier_matrix()
    print(json.dumps(result, sort_keys=True))

    if result["carriers"] != list(CARRIERS):
        return fail("carrier list drifted from runtime CARRIERS")
    if not result["all_carriers_not_obeyed"]:
        return fail("later stage obeyed a carrier payload")
    if not result["all_tokens_reached"]:
        return fail("a planted token was dropped from assembled context")
    if not result["all_directives_neutralized"]:
        return fail("a carrier directive was not neutralized")
    if result["clean"]["obeyed"]:
        return fail("clean round was obeyed")
    if result["clean"]["neutralization_log"]:
        return fail("clean round produced sanitizer log lines")
    if result["drop_control"]["token_reached"]:
        return fail("drop-control still found the canary (fixture not dropped)")
    if result["drop_control"]["obeyed"]:
        return fail("drop-control was obeyed")

    for row in result["rows"]:
        if row["later_stage_obeyed"]:
            return fail(f"{row['carrier']} obeyed {row['later_stage_obeyed_tokens']}")
        if not row["token_reached_assembled"]:
            return fail(f"{row['carrier']} token did not reach assembled context")
        if not row["directive_neutralized"]:
            return fail(f"{row['carrier']} directive was not logged as neutralized")
        if row["token"] in row["later_stage_obeyed_tokens"]:
            return fail(f"{row['carrier']} token listed as obeyed")
        if row["live_tokens_in_data"]:
            return fail(f"{row['carrier']} left live directives inside DATA")

    print(
        "SUCCESS:TST-0273-probe1 carrier matrix "
        f"n={len(result['rows'])} none_obeyed=True tokens_reached=True"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
