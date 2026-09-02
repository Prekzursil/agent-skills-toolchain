#!/usr/bin/env python3
"""Probe 2: leave a recused ballot in the tally; recomputation FIRES."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402
from tools.council.integrity.recusal import (  # noqa: E402
    RECUSED_BALLOT_IN_TALLY,
)

ART = REPO / "command-center/receipts/IMP-0361.json"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0361-probe2 {msg}")
    return 1


def main() -> int:
    nc = S.negative_control()
    print(json.dumps(nc, sort_keys=True))

    if nc["honest_fired"]:
        return fail("honest recompute counting set fired")
    if nc["honest_code"] != "SILENT":
        return fail(f"honest code {nc['honest_code']!r}")
    if not nc["planted_fired"]:
        return fail("planted recused-ballot tally did not fire")
    if nc["planted_code"] != RECUSED_BALLOT_IN_TALLY:
        return fail(f"planted code {nc['planted_code']!r}")
    if S.RECUSED not in nc["planted_leaked_seats"]:
        return fail(f"leaked seats {nc['planted_leaked_seats']}")
    if f"b-{S.RECUSED}-r{S.ROUND}" not in nc["planted_leaked_ballots"]:
        return fail(f"leaked ballots {nc['planted_leaked_ballots']}")
    if nc["recused_in_recomputed"]:
        return fail("recompute still counted the recused seat")
    if not nc["recused_in_recorded"]:
        return fail("recorded tally did not retain the recused ballot for comparison")
    if not nc["differ"]:
        return fail("recorded vs recomputed did not diverge")
    if not nc["both_states"]:
        return fail("both-states control collapsed")

    if not ART.is_file():
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0361" not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    measured = doc.get("measured") or {}
    nc_doc = measured.get("negative_control") or {}
    if nc_doc.get("planted_fired") is not True:
        return fail("receipt did not record planted_fired")
    if nc_doc.get("honest_fired") is not False:
        return fail("receipt did not record honest silent")
    if nc_doc.get("code") != RECUSED_BALLOT_IN_TALLY:
        return fail("receipt negative-control code drift")

    ids = doc.get("negative_control_ids") or []
    if "IMP-0361-NC-RECUSED-BALLOT-IN-TALLY" not in ids:
        return fail("receipt missing negative_control_ids row")

    print(
        f"planted_fired=True honest_fired=False code={RECUSED_BALLOT_IN_TALLY} "
        f"leaked={nc['planted_leaked_seats']}"
    )
    print("SUCCESS:IMP-0361-probe2 recused-ballot-in-tally FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
