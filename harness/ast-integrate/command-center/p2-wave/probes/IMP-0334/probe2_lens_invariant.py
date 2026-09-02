#!/usr/bin/env python3
"""Probe 2: lens-invariant output must be flagged, not accepted as compliance.

Both-states:
  * LensFaithfulSpeaker is silent (compliant, no role-collapse).
  * InvariantSpeaker(spam_vocabulary=True) fires ROLE_COLLAPSE even though
    every assigned-lens marker is present in the turn text.

A vocab-only checker would accept the spam fixture. The divergence
gate must still refuse it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from scenario import ARTIFACT, PARTICIPANTS, QUESTION, SENTINEL  # noqa: E402
from tools.council.protocol.hats import (  # noqa: E402
    REASON_ROLE_COLLAPSE,
    HatsEngine,
    InvariantSpeaker,
    LensFaithfulSpeaker,
    ROLE_COLLAPSE_MAX_DISTANCE,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0334-probe2 {msg}")
    return 1


def main() -> int:
    engine = HatsEngine(mode="parallel")
    good = engine.run(PARTICIPANTS, QUESTION, LensFaithfulSpeaker())
    bad = engine.run(
        PARTICIPANTS, QUESTION, InvariantSpeaker(spam_vocabulary=True)
    )
    bare = engine.run(
        PARTICIPANTS, QUESTION, InvariantSpeaker(spam_vocabulary=False)
    )

    payload = {
        "probe": "probe2-lens-invariant",
        "unit_id": "IMP-0334",
        "threshold": ROLE_COLLAPSE_MAX_DISTANCE,
        "good_compliant": good.compliant,
        "good_flagged": good.role_collapse_flagged,
        "good_vocab_ok": good.vocabulary.all_present,
        "good_mean_across_lens": good.divergence.to_dict()["mean_across_lens"],
        "good_peer_baseline": good.divergence.across_participant_baseline,
        "bad_compliant": bad.compliant,
        "bad_flagged": bad.role_collapse_flagged,
        "bad_vocab_ok": bad.vocabulary.all_present,
        "bad_reasons": list(bad.reasons),
        "bad_mean_across_lens": bad.divergence.to_dict()["mean_across_lens"],
        "bad_peer_baseline": bad.divergence.across_participant_baseline,
        "bad_collapsed": list(bad.divergence.role_collapse_participants),
        "bare_flagged": bare.role_collapse_flagged,
        "bare_vocab_ok": bare.vocabulary.all_present,
        "both_states_diverge": (
            good.compliant is True and bad.compliant is False
        ),
        "pass": False,
    }
    ok = (
        good.compliant
        and not good.role_collapse_flagged
        and good.vocabulary.all_present
        and good.divergence.to_dict()["mean_across_lens"]
        > ROLE_COLLAPSE_MAX_DISTANCE
        and not bad.compliant
        and bad.role_collapse_flagged
        and bad.vocabulary.all_present
        and REASON_ROLE_COLLAPSE in bad.reasons
        and set(bad.divergence.role_collapse_participants) == set(PARTICIPANTS)
        and all(
            dist <= ROLE_COLLAPSE_MAX_DISTANCE
            for dist in bad.divergence.per_participant_across_lens.values()
        )
        and bare.role_collapse_flagged
        and not bare.vocabulary.all_present
        and payload["both_states_diverge"]
    )
    payload["pass"] = bool(ok)
    print(json.dumps(payload, sort_keys=True))

    if not good.compliant:
        return fail(f"faithful not compliant reasons={list(good.reasons)}")
    if good.role_collapse_flagged:
        return fail("faithful speaker flagged as role-collapse")
    if not good.vocabulary.all_present:
        return fail("faithful vocab misses")
    if good.divergence.to_dict()["mean_across_lens"] <= ROLE_COLLAPSE_MAX_DISTANCE:
        return fail("faithful across-lens divergence below collapse threshold")
    if bad.compliant:
        return fail("vocab-spamming invariant speaker accepted as compliant")
    if not bad.role_collapse_flagged:
        return fail("vocab-spamming invariant speaker not flagged")
    if not bad.vocabulary.all_present:
        return fail("spam fixture must pass vocab so the collapse gate is the one that fires")
    if REASON_ROLE_COLLAPSE not in bad.reasons:
        return fail(f"missing {REASON_ROLE_COLLAPSE} in {list(bad.reasons)}")
    if set(bad.divergence.role_collapse_participants) != set(PARTICIPANTS):
        return fail("not every participant collapsed on the invariant fixture")
    if not bare.role_collapse_flagged:
        return fail("bare invariant speaker not flagged")
    if bare.vocabulary.all_present:
        return fail("bare invariant unexpectedly passed vocab")
    if good.compliant == bad.compliant:
        return fail("both-states did not diverge")

    art = REPO / ARTIFACT
    if not art.is_file():
        return fail("receipt missing")
    text = art.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    nc_ids = doc.get("negative_control_ids") or []
    if "IMP-0334-NC-lens-invariant-flagged" not in nc_ids:
        return fail("receipt missing negative control id")
    recorded = doc.get("negative_control") or {}
    if recorded.get("fired_on_bad_state") is not True:
        return fail("receipt did not record fire on invariant fixture")
    if recorded.get("silent_on_good_state") is not True:
        return fail("receipt did not record silence on faithful fixture")
    if recorded.get("bad_vocab_ok") is not True:
        return fail("receipt spam fixture vocab_ok drift")
    if recorded.get("bad_compliant") is not False:
        return fail("receipt accepted invariant as compliant")

    print(
        "both_states ok=True faithful_flagged=False spam_flagged=True "
        f"spam_vocab_ok=True mean_good={payload['good_mean_across_lens']} "
        f"mean_bad={payload['bad_mean_across_lens']}"
    )
    print("SUCCESS:IMP-0334-probe2 lens-invariant flagged not accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
