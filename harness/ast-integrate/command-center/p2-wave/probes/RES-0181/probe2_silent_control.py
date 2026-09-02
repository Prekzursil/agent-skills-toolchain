#!/usr/bin/env python3
"""Probe 2: silent history stays NO-RATIONALE-RECOVERABLE (both-states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import archaeology as A  # noqa: E402
from corpus import MECHANISMS, OUT_REL, SENTINEL, SILENT_IDS, UNIT_ID  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0181-probe2 {msg}")
    return 1


def main() -> int:
    out = REPO / OUT_REL
    if not out.is_file():
        return fail("artifact missing")
    doc = json.loads(out.read_text(encoding="utf-8"))
    if SENTINEL not in out.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    claims = {c.get("mechanism_id"): c for c in (doc.get("claims") or [])}
    missing = [i for i in SILENT_IDS if i not in claims]
    if missing:
        return fail(f"silent rows absent {missing}")

    live = A.recover_all()
    for sid in SILENT_IDS:
        row = claims[sid]
        if row.get("recovery_status") != A.NO_RATIONALE:
            return fail(
                f"{sid} artifact invented rationale status={row.get('recovery_status')}"
            )
        if row.get("history_quotes"):
            return fail(f"{sid} artifact carries quotes on silent history")
        if live[sid].get("recovery_status") != A.NO_RATIONALE:
            return fail(f"{sid} live engine recovered from silent captures")
        # Title bait: a tempting canonical name must not become a quote.
        mech = dict(next(m for m in MECHANISMS if m["id"] == sid))
        bait = mech.get("bait_title") or mech["canonical_mechanism"]
        silent_text, _ = A.join_captures(mech["history_capture_ids"])
        baited = A.recover_with_history_override(mech, bait + "\n" + silent_text)
        if baited["recovery_status"] != A.NO_RATIONALE:
            return fail(f"{sid} engine copied bait title into a rationale")

    # Both-states: inject an explicit needle+because quote into silent history.
    planted = []
    for sid in SILENT_IDS:
        mech = next(m for m in MECHANISMS if m["id"] == sid)
        needle = mech["history_needles"][0]
        silent_text, _ = A.join_captures(mech["history_capture_ids"])
        injected = (
            silent_text
            + f"\nthis exists because {needle} was required for the negative control.\n"
        )
        lit = A.recover_with_history_override(mech, injected)
        if lit["recovery_status"] != "RATIONALE-RECOVERED":
            return fail(f"{sid} detector silent in the LIT (planted-quote) state")
        planted.append(sid)

    counts = doc.get("counts") or {}
    if int(counts.get("silent_negative_control") or 0) != 3:
        return fail("counts.silent_negative_control != 3")
    if int(counts.get("no_rationale_recoverable_silent") or 0) != 3:
        return fail("silent count not 3")
    print(
        json.dumps(
            {
                "probe": "probe2-silent-control",
                "unit_id": UNIT_ID,
                "silent_ids": SILENT_IDS,
                "dark_state": A.NO_RATIONALE,
                "lit_state_recovered": planted,
                "title_bait_refused": True,
                "pass": True,
                "reviewer_id": "RES-0181-probe2-silent-control",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:RES-0181-probe2 silent controls stay NO-RATIONALE-RECOVERABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
