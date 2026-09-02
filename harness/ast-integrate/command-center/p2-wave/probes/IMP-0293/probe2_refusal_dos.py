#!/usr/bin/env python3
"""Named probe 2: perpetual-refusal DoS plus negative control (IMP-0293).

Adversarial reviewer starting from the tests, not the author's summary:
  * three consecutive author REFUSEs of covering steelmans must escalate
    without deadlock
  * a mediator (not a party) can then accept; a strawman still cannot
  * negative control: disable the gate and the same strawman rebuttal
    is admitted, proving the reject path is sensitive
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _repo_root() -> Path:
    for p in [HERE, *HERE.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise SystemExit("FAILED:IMP-0293-probe2 repo root not found")


REPO = _repo_root()
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.steelman import (  # noqa: E402
    ESCALATION_KIND,
    REFUSAL_LIMIT,
    SteelmanGate,
)

POS = "pos-markets"
AUTHOR = "alice"
OPPONENT = "bob"
MEDIATOR = "mina"
CLAIMS = [
    {"id": "c1", "text": "Information asymmetry collapses markets."},
    {"id": "c2", "text": "Disclosure rules can restore price signals."},
]
COVERING = [
    {"id": "c1", "paraphrase": "Hidden quality makes markets unravel."},
    {"id": "c2", "paraphrase": "Disclosure can restore informative prices."},
]
STEEL = (
    "Alice's position is that hidden quality unravels markets and that "
    "disclosure rules can restore price signals."
)
STRAW = "Alice is a regulation maximalist; ignore the claims."
REAL = "Granting both claims, enforcement costs can dominate in thin markets."


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0293-probe2 {msg}")
    return 1


def _register(g: SteelmanGate) -> None:
    g.register_position(
        position_id=POS,
        author_id=AUTHOR,
        claims=CLAIMS,
        text="Markets fail under hidden quality; disclosure restores signals.",
    )


def main() -> int:
    g = SteelmanGate()
    _register(g)
    if g.refusal_limit != REFUSAL_LIMIT or REFUSAL_LIMIT != 3:
        return fail(f"refusal_limit is {g.refusal_limit}, want 3")

    last = None
    for i in range(3):
        sm = g.submit_steelman(
            position_id=POS,
            opponent_id=OPPONENT,
            text=f"{STEEL} #{i+1}",
            restatement=COVERING,
        )
        if not sm.get("structural_ok"):
            return fail(f"covering steelman {i+1} marked incomplete")
        last = g.author_verdict(
            attempt_id=sm["attempt_id"],
            actor_id=AUTHOR,
            accepted=False,
            rationale=f"refuse {i+1}",
        )
    if last is None or not last.get("escalated"):
        return fail("three refusals did not escalate")
    if last.get("deadlock") or g.deadlocked(POS, OPPONENT):
        return fail("perpetual refusal deadlocked the session")
    esc = last.get("escalation") or {}
    if esc.get("escalation_kind") != ESCALATION_KIND:
        return fail(f"escalation kind {esc.get('escalation_kind')!r}")
    if esc.get("deadlock") is not False:
        return fail("escalation record did not set deadlock=False")
    if g.progress_state(POS, OPPONENT) != "escalated":
        return fail("progress_state is not escalated")

    still_blocked = g.submit_rebuttal(
        position_id=POS, opponent_id=OPPONENT, text=STRAW
    )
    if still_blocked.get("admitted"):
        return fail("escalation auto-opened a strawman rebuttal")

    sm4 = g.submit_steelman(
        position_id=POS,
        opponent_id=OPPONENT,
        text=f"{STEEL} #4",
        restatement=COVERING,
    )
    author_again = g.author_verdict(
        attempt_id=sm4["attempt_id"], actor_id=AUTHOR, accepted=True
    )
    if author_again.get("ok"):
        return fail("author still held exclusive-accept after escalation")

    party = g.appoint_mediator(
        position_id=POS, opponent_id=OPPONENT, mediator_id=OPPONENT
    )
    if party.get("ok"):
        return fail("opponent was appointed mediator")
    med = g.appoint_mediator(
        position_id=POS, opponent_id=OPPONENT, mediator_id=MEDIATOR
    )
    if not med.get("ok"):
        return fail("third-party mediator appointment failed")
    accepted = g.author_verdict(
        attempt_id=sm4["attempt_id"], actor_id=MEDIATOR, accepted=True
    )
    if not accepted.get("ok"):
        return fail("mediator could not accept after escalation")
    admitted = g.submit_rebuttal(
        position_id=POS, opponent_id=OPPONENT, text=REAL
    )
    if not admitted.get("admitted"):
        return fail("rebuttal still blocked after mediator accept")

    # Negative control: same strawman, gate removed, must pass.
    off = SteelmanGate(gate_enabled=False)
    _register(off)
    control = off.submit_rebuttal(
        position_id=POS, opponent_id=OPPONENT, text=STRAW
    )
    if not control.get("admitted"):
        return fail("negative control: gate-off strawman was still rejected")
    if control["record"].get("preceded_by_accepted_steelman"):
        return fail("negative control claimed a steelman that was never filed")

    payload = {
        "probe": "probe2-refusal-dos-and-negative-control",
        "unit_id": "IMP-0293",
        "refusals": 3,
        "escalated": True,
        "deadlock": False,
        "escalation_kind": esc.get("escalation_kind"),
        "escalation_events": len(g.escalation_events()),
        "strawman_still_blocked_after_escalation": not still_blocked.get("admitted"),
        "mediator_unblocked": bool(admitted.get("admitted")),
        "negative_control_gate_off_admitted": bool(control.get("admitted")),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "escalated=True deadlock=False mediator_unblocked=True "
        "negative_control_admitted=True"
    )
    print("SUCCESS:IMP-0293-probe2 perpetual-refusal DoS and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
