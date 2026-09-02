#!/usr/bin/env python3
"""Probe 1: role-drift both-states + use-vs-mention + negative control.

Planted-bad = synthesiser injects P-SYNTH -> FIRES.
Known-good = closed-world select/address -> SILENT.
Mention-only = prose names P-HYPOTHETICAL without minting -> SILENT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import schema_val as S  # noqa: E402
import triad as T  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md"
)


def main() -> int:
    good = T.check(F.known_good())
    bad = T.check(F.planted_new_proposal())
    third = T.check(F.planted_new_objection())
    mention = T.check(F.mention_only())
    critic = T.check(F.critic_proposes())
    cover = T.check(F.coverage_plus_mint())

    print("PLANTED-BAD new-proposal: " + T.fmt(bad))
    print("PLANTED-BAD new-objection: " + T.fmt(third))
    print("KNOWN-GOOD closed-world: " + T.fmt(good))
    print("MENTION-ONLY: " + T.fmt(mention))
    print("CRITIC-PROPOSES: " + T.fmt(critic))
    print("COVERAGE-PLUS-MINT: " + T.fmt(cover))

    if not bad["fires"]:
        print("FAILED:CNL-0027-probe1 planted new-proposal did not FIRE")
        return 1
    if "P-SYNTH" not in bad["minted_option_ids"] and "new_proposal" not in bad["forbidden_hits"]:
        print("FAILED:CNL-0027-probe1 P-SYNTH not attributed")
        return 1
    if not third["fires"]:
        print("FAILED:CNL-0027-probe1 planted new-objection did not FIRE")
        return 1
    if good["fires"]:
        print("FAILED:CNL-0027-probe1 known-good was not SILENT")
        return 1
    if mention["fires"]:
        print("FAILED:CNL-0027-probe1 mention-only FIRED (use-vs-mention miss)")
        return 1
    if not critic["fires"]:
        print("FAILED:CNL-0027-probe1 critic-as-proposer did not FIRE")
        return 1
    if cover["coverage"] != good["coverage"]:
        print("FAILED:CNL-0027-probe1 coverage-plus-mint coverage should match known-good")
        return 1
    if abs(cover["coverage"] - 1.0) > 1e-12:
        print(f"FAILED:CNL-0027-probe1 coverage-plus-mint coverage {cover['coverage']} != 1")
        return 1
    if not cover["fires"] or cover["joint"] != 0.0:
        print("FAILED:CNL-0027-probe1 coverage-plus-mint must FIRE with joint=0")
        return 1
    if good["joint"] != 1.0:
        print("FAILED:CNL-0027-probe1 known-good joint is not 1.0")
        return 1

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:CNL-0027" not in ART.read_text(encoding="utf-8"):
            print("FAILED:CNL-0027-probe1 sentinel absent")
            return 1
        rec = S.fixture_scores(doc)
        rec_bad = rec.get("planted_new_proposal") or {}
        rec_good = rec.get("known_good") or {}
        if rec_bad.get("fires") is not True or rec_good.get("fires") is not False:
            print("FAILED:CNL-0027-probe1 artifact both-states drift")
            return 1

    print(
        "NEGATIVE CONTROL verbatim: on planted-new-proposal the check FIRES "
        f"(reason={bad['reason']}, minted_opt={bad['minted_option_ids']}); "
        "it does not stay silent and it does not treat a minted option as a citation."
    )
    print(
        "BOTH-STATES: FIRED on planted-bad synthesiser-as-proposer; "
        "SILENT on known-good closed-world; mention-only SILENT"
    )
    print("SUCCESS:CNL-0027-probe1 role-drift both-states mention-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
