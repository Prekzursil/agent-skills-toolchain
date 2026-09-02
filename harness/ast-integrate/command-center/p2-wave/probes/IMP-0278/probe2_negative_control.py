#!/usr/bin/env python3
"""Named probe 2: negative control — disable redaction and assert the scan FIRES.

Starts from the tests, not an author summary: load the same fixture, turn
redaction off, deliver prompts, scan for tokens that the redacting spec
withholds. The scan must fire. The redacting path must stay silent so this
is a both-states control, not a constant-firing detector.

Also re-proves the detector control on the open (unredacted) packet: a
token that was delivered is found before we trust any other silence.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.integrity.partition import (  # noqa: E402
    detector_control,
    deliver_all,
    load_spec,
    scan_delivered,
    scan_text,
    tokens_withheld,
)

FIXTURE = HERE / "fixtures" / "scenario.json"


def open_variant(spec: dict) -> dict:
    """Redaction-off variant: every fact visible to every seat.

    The re-authored partition module drives visibility purely through fact
    partitions (no spec-level redact switch), so 'redaction off' is expressed
    by widening every fact to the wildcard partition.
    """
    out = copy.deepcopy(spec)
    out["redact"] = False
    for fact in out.get("facts") or []:
        fact["partitions"] = ["*"]
    return out


def main() -> int:
    redacting = load_spec(FIXTURE)
    if redacting.get("redact") is not True:
        print("FAILED:IMP-0278-probe2 fixture redact is already off")
        return 1

    good_delivered = deliver_all(redacting)
    good_hits = scan_delivered(redacting, good_delivered)

    open_spec = open_variant(redacting)
    bad_delivered = deliver_all(open_spec)

    # Tokens the *redacting* spec withholds from alice must appear in the
    # unredacted alice prompt, and the same scan_text used in production
    # must report them. We do not consult a precomputed leaks=0 flag.
    originally_withheld_alice = list(tokens_withheld(redacting, "alice"))
    alice_open = bad_delivered["alice"].prompt
    fired_tokens = scan_text(alice_open, originally_withheld_alice)

    # Full-engine scan on the open spec: withheld set is empty (redact off),
    # so scan_delivered(open_spec) is silent by construction. That would be
    # a vacuous green. The negative control therefore scans the OPEN prompts
    # against the REDACTING withheld set.
    cross_hits = []
    for seat in redacting["seats"]:
        sid = seat["seat_id"]
        withheld = tokens_withheld(redacting, sid)
        found = scan_text(bad_delivered[sid].prompt, withheld)
        for tok in found:
            cross_hits.append({"seat_id": sid, "token": tok})

    # Detector control on open packet: alice still has her own alpha token.
    alpha_token = "PTOK-ALPHA-imp0278-7f3a"
    control_ok = detector_control(alice_open, alpha_token)

    # Observer's joint token is withheld under redaction and must appear
    # when redaction is off (joint is alpha+beta, not gamma).
    joint = "PTOK-JOINT-imp0278-ab22"
    observer_open_has_joint = joint in bad_delivered["observer"].prompt
    observer_closed_has_joint = joint in good_delivered["observer"].prompt

    silent_on_good = len(good_hits) == 0
    fired_on_bad = len(fired_tokens) > 0 and len(cross_hits) > 0

    payload = {
        "probe": "probe2-negative-control",
        "unit_id": "IMP-0278",
        "alice_originally_withheld": originally_withheld_alice,
        "alice_open_scan_hits": fired_tokens,
        "cross_seat_open_hits": cross_hits,
        "good_path_leak_hits": len(good_hits),
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "detector_control_on_open_packet": control_ok,
        "observer_closed_has_joint": observer_closed_has_joint,
        "observer_open_has_joint": observer_open_has_joint,
        "vacuous_scan_delivered_on_open_spec_hits": len(
            scan_delivered(open_spec, bad_delivered)
        ),
        "note": (
            "scan_delivered(open_spec) is empty because the open spec withholds "
            "nothing; the negative control therefore applies the redacting "
            "withheld set to the open prompts."
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    if not silent_on_good:
        print("FAILED:IMP-0278-probe2 redacting path leaked")
        return 1
    if not fired_on_bad:
        print("FAILED:IMP-0278-probe2 disabling redaction did not make the scan FIRE")
        return 1
    if not control_ok:
        print("FAILED:IMP-0278-probe2 detector control failed on open packet")
        return 1
    if observer_closed_has_joint:
        print("FAILED:IMP-0278-probe2 observer saw joint token under redaction")
        return 1
    if not observer_open_has_joint:
        print("FAILED:IMP-0278-probe2 observer open packet missing joint token")
        return 1
    expected_alice_withheld = {
        "PTOK-BETA-imp0278-4d81",
        "PTOK-GAMMA-imp0278-91bc",
    }
    if set(originally_withheld_alice) != expected_alice_withheld:
        print("FAILED:IMP-0278-probe2 unexpected withheld set for alice")
        return 1
    if not expected_alice_withheld.issubset(set(fired_tokens)):
        print("FAILED:IMP-0278-probe2 alice open scan missed a withheld token")
        return 1
    print(
        "SUCCESS:IMP-0278-probe2 negative-control scan FIRES with redaction off "
        f"alice_hits={fired_tokens} silent_on_good={silent_on_good}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
