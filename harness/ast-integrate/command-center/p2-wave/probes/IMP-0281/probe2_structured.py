#!/usr/bin/env python3
"""Probe 2: structured-action pass, use-vs-mention control, breach must fire.

TEST_REQUIREMENT=use-vs-mention control: quoted text describing a vote must NOT be classified as a vote
TEST_REQUIREMENT=negative control: an actual breach must FIRE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from corpus import TURNS  # noqa: E402
from tools.council.roles.guard import RoleGuard  # noqa: E402

UNIT = "IMP-0281"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def by_id(tid: str) -> dict:
    for row in TURNS:
        if row["id"] == tid:
            return row
    raise KeyError(tid)


def main() -> int:
    print(f"{UNIT} STRUCTURED ACTION / USE-VS-MENTION / NEGATIVE CONTROL")
    print(
        "TEST_REQUIREMENT=use-vs-mention control: quoted text describing a vote "
        "must NOT be classified as a vote"
    )
    print("TEST_REQUIREMENT=negative control: an actual breach must FIRE")

    guard = RoleGuard()

    # --- Pass 2: structured action is authoritative, even when prose disagrees.
    disagreements: list[dict] = []
    for turn in TURNS:
        if not turn.get("action"):
            continue
        prose = guard.inspect_prose(turn)
        structured = guard.inspect_structured(turn)
        final = guard.inspect(turn)
        row = {
            "id": turn["id"],
            "action": turn["action"],
            "gold": turn["gold"],
            "prose_rejected": prose.rejected,
            "structured_rejected": structured.rejected,
            "final_rejected": final.rejected,
            "final_source": final.source,
        }
        if prose.rejected != structured.rejected:
            disagreements.append(row)
        if final.source != "structured":
            return fail(f"{turn['id']} had action={turn['action']!r} but source={final.source}")
        if final.rejected != structured.rejected:
            return fail(f"{turn['id']} final did not follow structured pass")

    needed = {"T07", "T14", "T16", "T35", "T36"}
    got = {r["id"] for r in disagreements}
    if not needed.issubset(got):
        return fail(f"structured/prose disagreements {sorted(got)} missing {sorted(needed - got)}")

    t35 = by_id("T35")
    if guard.inspect_prose(t35).rejected is not True:
        return fail("T35 prose must treat 'I vote …' as a vote")
    if guard.inspect_structured(t35).rejected is not False:
        return fail("T35 structured action=speak must allow")
    t07 = by_id("T07")
    if guard.inspect_prose(t07).rejected is not False:
        return fail("T07 prose (no performative) must allow")
    if guard.inspect_structured(t07).rejected is not True:
        return fail("T07 structured action=propose on critic must FIRE")

    print(
        json.dumps(
            {
                "structured_prose_disagreements": disagreements,
                "pass": "structured-overrides-prose",
            },
            sort_keys=True,
        )
    )

    # --- Use-vs-mention: quoted vote is not a vote.
    quoted = by_id("T25")
    quoted_ok = guard.inspect(quoted)
    if quoted_ok.rejected or quoted_ok.attempted_action == "vote":
        return fail(f"quoted vote classified as vote: {quoted_ok}")
    blockquote = by_id("T38")
    if guard.inspect(blockquote).rejected:
        return fail("blockquote vote was classified as a vote")
    print("use_vs_mention_quoted_vote_not_classified_as_vote=True")

    # Both-states: quote stripping is load-bearing.
    mutant = guard.inspect_prose(quoted, strip_quotes=False)
    if not mutant.rejected or mutant.attempted_action != "vote":
        return fail(f"quote-strip mutant did not fire on quoted vote: {mutant}")
    print("both_states_quote_strip_mutant_fires=True silent_on_stripped=True")

    # --- Negative control: an actual breach must FIRE and be recorded.
    ledger_guard = RoleGuard()
    live_breach = by_id("T10")
    fired = ledger_guard.enforce(live_breach)
    if not fired.rejected or fired.attempted_action != "vote":
        return fail(f"actual non-voter vote did not FIRE: {fired}")
    if not fired.rejection:
        return fail("rejection was not recorded on the result")
    recs = ledger_guard.rejections()
    if len(recs) != 1 or recs[0]["turn_id"] != "T10":
        return fail(f"ledger {recs}")
    critic_propose = ledger_guard.enforce(by_id("T01"))
    if not critic_propose.rejected or critic_propose.attempted_action != "propose":
        return fail(f"critic proposing did not FIRE: {critic_propose}")
    print(
        json.dumps(
            {
                "negative_control_fired": True,
                "recorded_rejections": ledger_guard.rejections(),
            },
            sort_keys=True,
        )
    )

    print(f"SUCCESS:{UNIT}-probe2 structured-pass use-vs-mention negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
