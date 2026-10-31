#!/usr/bin/env python3
"""Named probe 1: veto, consent, late objection, window expiry."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.vote.consent import (  # noqa: E402
    ArtifactValidationError,
    ConsentSession,
    LATE_RECORD_AND_IGNORE,
    MODE_CONSENT,
    MODE_VETO,
    OUT_BLOCKED,
    OUT_CONSENTED,
    OUT_VETOED,
    RESP_CONSENT,
    RESP_OBJECT,
    RESP_VETO,
    SILENCE_IS_CONSENT,
    STATE_CONSENT_BY_SILENCE,
)

ART = REPO / "command-center" / "receipts" / "IMP-0306.json"
WINDOW = {"opens_at": 1000.0, "closes_at": 2000.0, "timezone": "UTC"}
SEATS = [
    {"id": "alice", "veto_right": True},
    {"id": "bob", "veto_right": False},
    {"id": "cara", "veto_right": False},
]


def session(mode: str = MODE_CONSENT) -> ConsentSession:
    return ConsentSession(
        proposal_id="probe1-imp-0306",
        mode=mode,
        silence_policy=SILENCE_IS_CONSENT,
        late_objection_policy=LATE_RECORD_AND_IGNORE,
        objection_window=WINDOW,
        participants=SEATS,
        proposal="probe1 live modes",
    )


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0306-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0306-probe1 receipt unparseable {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:IMP-0306-probe1 receipt not an object")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print(f"FAILED:IMP-0306-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0306" not in text:
        print("FAILED:IMP-0306-probe1 sentinel absent")
        return 1

    veto = session(MODE_VETO)
    veto.respond("alice", RESP_VETO, 1500, "holder veto")
    veto_art = veto.close(2000)
    if veto_art["outcome"] != OUT_VETOED:
        print(f"FAILED:IMP-0306-probe1 veto outcome {veto_art['outcome']}")
        return 1

    consent = session()
    consent.respond("alice", RESP_CONSENT, 1100, "explicit")
    consent_art = consent.close(2000)
    if consent_art["outcome"] != OUT_CONSENTED:
        print(f"FAILED:IMP-0306-probe1 consent outcome {consent_art['outcome']}")
        return 1
    if consent_art.get("silence_policy") != SILENCE_IS_CONSENT:
        print("FAILED:IMP-0306-probe1 silence_policy not on artifact")
        return 1
    win = consent_art.get("objection_window") or {}
    if win.get("opens_at") != 1000.0 or win.get("closes_at") != 2000.0:
        print(f"FAILED:IMP-0306-probe1 window {win}")
        return 1
    for seat in ("bob", "cara"):
        st = (consent_art.get("per_participant_state") or {}).get(seat) or {}
        if st.get("status") != STATE_CONSENT_BY_SILENCE:
            print(f"FAILED:IMP-0306-probe1 {seat} status {st}")
            return 1

    late = session()
    late.respond("alice", RESP_CONSENT, 1100, "explicit")
    late.close(2000)
    late_rec = late.respond("bob", RESP_OBJECT, 2500, "after close")
    late_art = late.to_artifact()
    if late_rec.get("admitted") is not False or late_art["outcome"] != OUT_CONSENTED:
        print(
            f"FAILED:IMP-0306-probe1 late handling rec={late_rec} out={late_art['outcome']}"
        )
        return 1
    if not late_art.get("late_objections"):
        print("FAILED:IMP-0306-probe1 late_objections empty")
        return 1

    blocked = session()
    blocked.respond("alice", RESP_CONSENT, 1100, "yes")
    blocked.respond("bob", RESP_OBJECT, 1600, "in-window admissible objection")
    blocked_art = blocked.close(2000)
    if blocked_art["outcome"] != OUT_BLOCKED:
        print(f"FAILED:IMP-0306-probe1 in-window objection {blocked_art['outcome']}")
        return 1

    early = session()
    early.respond("alice", RESP_CONSENT, 1100, "yes")
    try:
        early.close(1500)
        print("FAILED:IMP-0306-probe1 early close with silent seats was allowed")
        return 1
    except ArtifactValidationError:
        pass

    payload = {
        "late_admitted": late_rec.get("admitted"),
        "late_outcome_unchanged": late_art["outcome"] == OUT_CONSENTED,
        "pass": True,
        "probe": "probe1-modes",
        "silence_converted": ["bob", "cara"],
        "unit_id": "IMP-0306",
        "veto_outcome": veto_art["outcome"],
        "window_recorded": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "veto=VETOED consent=CONSENTED late_ignored=True "
        "silence_explicit_on_artifact=True early_close_refused=True"
    )
    print("SUCCESS:IMP-0306-probe1 veto consent late-objection window-expiry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
