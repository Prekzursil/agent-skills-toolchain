#!/usr/bin/env python3
"""Named probe 1: both-states silent/engaged + filler acks + exclusion from tally."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council" / "budget"))

from engagement import run_session  # noqa: E402
from fixtures import ack_filler, engaged_clean, silent_never_engaged  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0276.json"
SENTINEL = "SUCCESS:TST-0276"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0276-probe1 {msg}")
    return 1


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size < 128:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fail(f"unparseable {exc}")
    if SENTINEL not in text:
        return _fail("sentinel-absent")
    state = str(doc.get("state") or "").upper()
    if state in NOT_DELIVERING:
        return _fail(f"self-declared:{state}")
    if doc.get("unit_id") != "TST-0276":
        return _fail(f"unit_id {doc.get('unit_id')}")
    return 0


def _seat(result: dict, sid: str) -> dict:
    for row in result["seats"]:
        if row["seat_id"] == sid:
            return row
    raise KeyError(sid)


def main() -> int:
    if _check_artifact() != 0:
        return 1

    silent = run_session(silent_never_engaged())
    clean = run_session(engaged_clean())
    filler = run_session(ack_filler())

    ghost = _seat(silent, "ghost")
    if ghost["status"] != "ABSENT" or ghost["action"] == "NONE":
        return _fail(f"silent seat not escalated {ghost}")
    if ghost["counted_as_agreeing"] is True:
        return _fail("silent seat counted as agreeing")
    if "ghost" in silent["tally"]["agree_seat_ids"]:
        return _fail("ghost in agree set")
    if "ghost" in silent["tally"]["engaged_seat_ids"]:
        return _fail("ghost in engaged denominator")
    if silent["tally"]["numerator"] != 1 or silent["tally"]["denominator"] != 2:
        return _fail(f"silent tally {silent['tally']}")
    if abs((silent["tally"]["consensus_figure"] or 0) - 0.5) > 1e-9:
        return _fail(f"silent figure {silent['tally']['consensus_figure']}")
    if not silent["escalations"]:
        return _fail("escalation record empty")
    defect = silent["tally"]["defect_if_silence_were_consent"]["figure"]
    if defect is None or abs(defect - (2 / 3)) > 1e-9:
        return _fail(f"defect contrast missing {defect}")
    if silent["tally"]["consensus_figure"] == defect:
        return _fail("official figure equals silence-as-consent defect")

    if clean["escalations"]:
        return _fail(f"clean fixture escalated {clean['escalations']}")
    if clean["any_inactivity_fired"]:
        return _fail("inactivity path fired on engaged seats")
    if clean["engaged_inactivity_fired"]:
        return _fail("engaged_inactivity_fired on clean fixture")
    if silent["any_inactivity_fired"] == clean["any_inactivity_fired"]:
        return _fail("both-states inactivity did not discriminate")
    if abs((clean["tally"]["consensus_figure"] or 0) - (2 / 3)) > 1e-9:
        return _fail(f"clean figure {clean['tally']['consensus_figure']}")

    ghost_f = _seat(filler, "ghost")
    if ghost_f["status"] != "ABSENT":
        return _fail("ack-filler ghost counted as engaged")
    if "filler" not in ghost_f["reason"]:
        return _fail(f"ack-filler reason {ghost_f['reason']}")
    if ghost_f["counted_as_agreeing"] is True:
        return _fail("ack-filler counted as agreeing")

    payload = {
        "probe": "probe1-both-states",
        "unit_id": "TST-0276",
        "silent": {
            "figure": silent["tally"]["consensus_figure"],
            "absent": silent["tally"]["absent_seat_ids"],
            "agree": silent["tally"]["agree_seat_ids"],
            "escalations": silent["escalations"],
            "defect_figure": defect,
        },
        "clean": {
            "figure": clean["tally"]["consensus_figure"],
            "escalations": clean["escalations"],
            "inactivity_fired": clean["any_inactivity_fired"],
        },
        "filler": {
            "ghost_status": ghost_f["status"],
            "reason": ghost_f["reason"],
        },
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "silent_figure=%s ghost_status=%s clean_inactivity=%s filler=%s"
        % (
            silent["tally"]["consensus_figure"],
            ghost["status"],
            clean["any_inactivity_fired"],
            ghost_f["status"],
        )
    )
    print("SUCCESS:TST-0276-probe1 both-states silent escalated, engaged silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
