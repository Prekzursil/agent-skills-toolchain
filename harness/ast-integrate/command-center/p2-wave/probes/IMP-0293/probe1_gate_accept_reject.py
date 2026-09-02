#!/usr/bin/env python3
"""Named probe 1: steelman-gate accept and reject paths (IMP-0293).

Live evidence: a rejection log carrying the steelman text and the author's
verdict. Negative twin in the same run: after the author accepts a covering
steelman, the same opponent's rebuttal is admitted.
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
    raise SystemExit("FAILED:IMP-0293-probe1 repo root not found")


REPO = _repo_root()
sys.path.insert(0, str(REPO / "tools"))

from council.protocol.steelman import (  # noqa: E402
    ACCEPT,
    NONE,
    REFUSE,
    SteelmanGate,
)

POS = "pos-markets"
AUTHOR = "alice"
OPPONENT = "bob"
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
    print(f"FAILED:IMP-0293-probe1 {msg}")
    return 1


def main() -> int:
    g = SteelmanGate()
    g.register_position(
        position_id=POS,
        author_id=AUTHOR,
        claims=CLAIMS,
        text="Markets fail under hidden quality; disclosure restores signals.",
    )

    bare = g.submit_rebuttal(position_id=POS, opponent_id=OPPONENT, text=STRAW)
    if bare.get("admitted") or bare.get("ok"):
        return fail("bare strawman rebuttal was admitted")
    if bare.get("steelman_text") is not None or bare.get("author_verdict") != NONE:
        return fail("bare reject log was not empty/NONE")

    token = g.submit_steelman(
        position_id=POS,
        opponent_id=OPPONENT,
        text="Sure, anyway.",
        restatement=[{"id": "c1", "paraphrase": "ok"}],
    )
    if token.get("ok") or token.get("structural_ok"):
        return fail("token concession counted as a steelman")
    token_accept = g.author_verdict(
        attempt_id=token["attempt_id"], actor_id=AUTHOR, accepted=True
    )
    if token_accept.get("ok"):
        return fail("author was allowed to rubber-stamp a token concession")

    covering = g.submit_steelman(
        position_id=POS, opponent_id=OPPONENT, text=STEEL, restatement=COVERING
    )
    if not covering.get("structural_ok"):
        return fail("covering restatement marked incomplete")
    refused = g.author_verdict(
        attempt_id=covering["attempt_id"],
        actor_id=AUTHOR,
        accepted=False,
        rationale="paraphrase of c2 inverted the causal claim",
    )
    if refused.get("status") != "REFUSED":
        return fail("author refuse did not record REFUSE")
    blocked = g.submit_rebuttal(position_id=POS, opponent_id=OPPONENT, text=STRAW)
    if blocked.get("admitted"):
        return fail("rebuttal admitted after author REFUSE")
    if blocked.get("steelman_text") != STEEL or blocked.get("author_verdict") != REFUSE:
        return fail("reject log missing steelman text or author REFUSE")

    covering2 = g.submit_steelman(
        position_id=POS,
        opponent_id=OPPONENT,
        text=STEEL + " (second)",
        restatement=COVERING,
    )
    peer = g.author_verdict(
        attempt_id=covering2["attempt_id"], actor_id="carol", accepted=True
    )
    if peer.get("ok"):
        return fail("peer accept was allowed")
    accepted = g.author_verdict(
        attempt_id=covering2["attempt_id"], actor_id=AUTHOR, accepted=True
    )
    if not accepted.get("ok") or accepted.get("status") != "ACCEPTED":
        return fail("author accept of covering steelman failed")
    admitted = g.submit_rebuttal(position_id=POS, opponent_id=OPPONENT, text=REAL)
    if not admitted.get("admitted"):
        return fail("rebuttal rejected after author ACCEPT")
    if admitted["record"].get("author_verdict") != ACCEPT:
        return fail("admitted rebuttal did not carry ACCEPT")

    log = g.rejection_log()
    refuse_rows = [
        r
        for r in log
        if r.get("event") == "REBUTTAL_REJECTED" and r.get("author_verdict") == REFUSE
    ]
    if not refuse_rows or refuse_rows[-1].get("steelman_text") != STEEL:
        return fail("rejection log lacks steelman text + author REFUSE pair")

    payload = {
        "probe": "probe1-gate-accept-reject",
        "unit_id": "IMP-0293",
        "bare_rejected": not bare.get("admitted"),
        "token_rejected": not token.get("ok"),
        "token_cannot_be_accepted": not token_accept.get("ok"),
        "refuse_blocks_rebuttal": not blocked.get("admitted"),
        "logged_steelman_text": blocked.get("steelman_text"),
        "logged_author_verdict": blocked.get("author_verdict"),
        "accept_admits_rebuttal": bool(admitted.get("admitted")),
        "peer_cannot_accept": not peer.get("ok"),
        "rejection_log_rows": len(log),
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "bare_rejected=True refuse_logged=True accept_admits=True "
        f"verdict={payload['logged_author_verdict']}"
    )
    print("SUCCESS:IMP-0293-probe1 gate accept/reject and rejection log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
