#!/usr/bin/env python3
"""Named probe 1: full 6x6 transition matrix, independently of pytest.

Signal: every illegal cell is refused; every legal cell (with owner approval
where gated) is accepted. Owner-gated disclose without approval stays put.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.disclosure import (  # noqa: E402
    LEGAL_TRANSITIONS,
    STATES,
    DisclosureRegistry,
    IllegalTransition,
    OwnerGated,
    State,
)

DETAIL = "PROBE1-MATRIX-DETAIL-MUST-STAY-IN-VAULT"


def bootstrap(reg: DisclosureRegistry, target: State) -> str:
    rec = reg.create("pkg.probe1", DETAIL, actor="reporter")
    aid = rec.id
    if target is State.REPORTED:
        return aid
    if target is State.TRIAGED:
        path = [State.TRIAGED]
    elif target is State.EMBARGOED:
        path = [State.TRIAGED, State.EMBARGOED]
    elif target is State.FIX_AVAILABLE:
        path = [State.TRIAGED, State.FIX_AVAILABLE]
    elif target is State.DISCLOSED:
        path = [State.TRIAGED, State.DISCLOSED]
    elif target is State.WITHDRAWN:
        path = [State.WITHDRAWN]
    else:
        raise AssertionError(target)
    for st in path:
        if st is State.DISCLOSED:
            reg.transition(aid, st, actor="owner", owner_approved=True)
        else:
            actor = "reporter" if st is State.WITHDRAWN else "triager"
            reg.transition(aid, st, actor=actor)
    return aid


def main() -> int:
    cells: list[dict] = []
    mismatches: list[dict] = []
    for frm in STATES:
        for to in STATES:
            reg = DisclosureRegistry()
            aid = bootstrap(reg, frm)
            legal = (frm, to) in LEGAL_TRANSITIONS
            try:
                reg.transition(aid, to, actor="owner", owner_approved=True)
                outcome = "accepted"
                err = None
            except IllegalTransition as exc:
                outcome = "refused-illegal"
                err = exc.code
            except OwnerGated as exc:
                outcome = "refused-owner"
                err = exc.code
            expected = "accepted" if legal else "refused-illegal"
            ok = outcome == expected
            row = {
                "from": frm.value,
                "to": to.value,
                "legal": legal,
                "outcome": outcome,
                "expected": expected,
                "ok": ok,
                "error": err,
                "state_after": reg.get(aid).state.value,
            }
            cells.append(row)
            if not ok:
                mismatches.append(row)

    # owner-gated: legal disclose without approval must not move state
    gated_ok = True
    gated_notes: list[str] = []
    for src in (State.TRIAGED, State.EMBARGOED, State.FIX_AVAILABLE):
        reg = DisclosureRegistry()
        aid = bootstrap(reg, src)
        try:
            reg.transition(aid, State.DISCLOSED, actor="owner", owner_approved=False)
            gated_ok = False
            gated_notes.append(f"{src.value}: accepted without approval")
        except OwnerGated:
            if reg.get(aid).state is not src:
                gated_ok = False
                gated_notes.append(f"{src.value}: state moved on refuse")
            else:
                gated_notes.append(f"{src.value}: refused-and-held")
        try:
            reg.transition(
                aid, State.DISCLOSED, actor="owner", owner_approved=False
            )
        except OwnerGated:
            pass
        else:
            gated_ok = False
            gated_notes.append(f"{src.value}: second attempt did not refuse")
        if reg.get(aid).state is not src:
            gated_ok = False
            gated_notes.append(f"{src.value}: retry mutated state")

    legal_n = sum(1 for c in cells if c["legal"])
    illegal_n = sum(1 for c in cells if not c["legal"])
    accepted_legal = sum(1 for c in cells if c["legal"] and c["ok"])
    refused_illegal = sum(1 for c in cells if (not c["legal"]) and c["ok"])

    print(
        json.dumps(
            {
                "cells": 36,
                "legal": legal_n,
                "illegal": illegal_n,
                "accepted_legal": accepted_legal,
                "refused_illegal": refused_illegal,
                "mismatches": mismatches,
                "owner_gated_ok": gated_ok,
                "owner_gated_notes": gated_notes,
            },
            sort_keys=True,
        )
    )
    if mismatches or not gated_ok or legal_n != 12 or illegal_n != 24:
        print("FAILED:IMP-0100-probe1 transition matrix")
        return 1
    if accepted_legal != 12 or refused_illegal != 24:
        print("FAILED:IMP-0100-probe1 counts")
        return 1
    print("SUCCESS:IMP-0100-probe1 full transition matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
