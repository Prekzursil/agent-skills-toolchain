#!/usr/bin/env python3
"""Named probe 2: independent recount + protocol distinction + quoted silence policy."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "council" / "budget"))

from engagement import (  # noqa: E402
    CONSENT_SILENCE_POLICY,
    PROTOCOL_CONSENT_NO_OBJECTION,
    PROTOCOL_EXPLICIT_BALLOT,
    run_session,
    scan_silence_policy_lines,
)
from fixtures import engaged_clean, protocol_window, silent_never_engaged  # noqa: E402
from recount import recount  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0276.json"
SENTINEL = "SUCCESS:TST-0276"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0276-probe2 {msg}")
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


def _figures_match(live: dict, indep: dict) -> bool:
    t = live["tally"]
    return (
        t["numerator"] == indep["numerator"]
        and t["denominator"] == indep["denominator"]
        and sorted(t["agree_seat_ids"]) == sorted(indep["agree"])
        and sorted(t["absent_seat_ids"]) == sorted(indep["absent"])
        and sorted(t["engaged_seat_ids"]) == sorted(indep["engaged"])
    )


def main() -> int:
    if _check_artifact() != 0:
        return 1

    silent_spec = silent_never_engaged()
    clean_spec = engaged_clean()
    ballot_spec = protocol_window(PROTOCOL_EXPLICIT_BALLOT)
    consent_spec = protocol_window(PROTOCOL_CONSENT_NO_OBJECTION)

    silent_live = run_session(silent_spec)
    clean_live = run_session(clean_spec)
    ballot_live = run_session(ballot_spec)
    consent_live = run_session(consent_spec)

    silent_rc = recount(silent_spec)
    clean_rc = recount(clean_spec)
    ballot_rc = recount(ballot_spec)
    consent_rc = recount(consent_spec)

    if not _figures_match(silent_live, silent_rc):
        return _fail(f"silent recount mismatch live={silent_live['tally']} rc={silent_rc}")
    if not _figures_match(clean_live, clean_rc):
        return _fail("clean recount mismatch")
    if not _figures_match(ballot_live, ballot_rc):
        return _fail("ballot recount mismatch")
    if not _figures_match(consent_live, consent_rc):
        return _fail("consent recount mismatch")

    if silent_rc["ghost_counted_as_agreeing"]:
        return _fail("independent recount folded ghost into agree")
    if silent_rc["figure"] != 0.5:
        return _fail(f"independent silent figure {silent_rc['figure']}")
    if not silent_rc["escalation_fires"]:
        return _fail("independent recount missed escalation")
    if clean_rc["absent"]:
        return _fail(f"independent clean absent {clean_rc['absent']}")
    if clean_live["any_inactivity_fired"]:
        return _fail("reviewer: inactivity fired on engaged-clean")
    if silent_live["any_inactivity_fired"] == clean_live["any_inactivity_fired"]:
        return _fail("reviewer both-states did not discriminate")

    bf = ballot_live["tally"]["consensus_figure"]
    cf = consent_live["tally"]["consensus_figure"]
    if bf == cf:
        return _fail(f"protocols did not differ ballot={bf} consent={cf}")
    if abs((bf or 0) - (2 / 3)) > 1e-9:
        return _fail(f"ballot figure {bf}")
    if abs((cf or 0) - 1.0) > 1e-9:
        return _fail(f"consent figure {cf}")
    if ballot_rc["roles"].get("analyst") != "ABSTAIN":
        return _fail(f"ballot analyst role {ballot_rc['roles']}")
    if consent_rc["roles"].get("analyst") != "NO_OBJECTION":
        return _fail(f"consent analyst role {consent_rc['roles']}")
    if "analyst" in ballot_live["tally"]["absent_seat_ids"]:
        return _fail("analyst was absent under ballot; need engaged-silent distinction")

    quotes = scan_silence_policy_lines()
    if len(quotes) < 2:
        return _fail(f"need both SILENCE_POLICY lines, got {quotes}")
    consent_hit = [q for q in quotes if "consent_no_objection" in q["text"]]
    ballot_hit = [q for q in quotes if "explicit_ballot" in q["text"]]
    if not consent_hit or not ballot_hit:
        return _fail(f"policy quotes incomplete {quotes}")
    if CONSENT_SILENCE_POLICY.split(":")[0] not in consent_hit[0]["text"]:
        return _fail("consent policy quote does not name the protocol")

    payload = {
        "probe": "probe2-independent-recount",
        "unit_id": "TST-0276",
        "silent_figure": silent_rc["figure"],
        "clean_absent": clean_rc["absent"],
        "ballot_figure": bf,
        "consent_figure": cf,
        "analyst_ballot_role": ballot_rc["roles"].get("analyst"),
        "analyst_consent_role": consent_rc["roles"].get("analyst"),
        "quoted_silence_policy": quotes,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "recount silent=%s ballot=%s consent=%s analyst=%s/%s"
        % (
            silent_rc["figure"],
            bf,
            cf,
            ballot_rc["roles"].get("analyst"),
            consent_rc["roles"].get("analyst"),
        )
    )
    print("SUCCESS:TST-0276-probe2 independent recount and protocol distinction")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
