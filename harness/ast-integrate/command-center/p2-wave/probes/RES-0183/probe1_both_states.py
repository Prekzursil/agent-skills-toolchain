#!/usr/bin/env python3
"""Probe 1: both-states control on the owner-constraint checker.

A public-canary draft under PR-ONLY must be flagged. A compliant PR-ONLY
draft must pass. A mention of the rejected alternative must not fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import checker as C  # noqa: E402
import extract as E  # noqa: E402

ART = (
    E.REPO
    / "command-center/research/sources-frontier/"
    / "RES-0183-owner-decision-log-as-a-source-class.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0183-probe1 {msg}")
    return 1


def main() -> int:
    blob = E.build_constraints()
    drafts = C.load_drafts()
    results = {name: C.check_draft(d, blob) for name, d in drafts.items()}
    print(json.dumps(results, indent=2)[:4000])

    bad = results["noncompliant_public_canary"]
    if bad["compliant"]:
        return fail("public canary draft was not flagged")
    if not any(v["constraint_id"] == "BC-OQ-3-PR-ONLY" for v in bad["violations"]):
        return fail("public canary was not attributed to BC-OQ-3-PR-ONLY")

    good = results["compliant_pr_only"]
    if not good["compliant"]:
        return fail(f"compliant PR-ONLY draft flagged {good['violations']}")

    mention = results["mention_rejected_canary"]
    if not mention["compliant"]:
        return fail("mention-only draft flagged")

    priv = results["noncompliant_private_canary"]
    if priv["compliant"]:
        return fail("private canary draft was not flagged")

    tranche = results["noncompliant_38_as_prompt_two"]
    if tranche["compliant"]:
        return fail("38-item Prompt Two draft was not flagged")

    live_bad = C.check_draft(
        "Propose a public canary under the current PR-ONLY release mode.",
        blob,
    )
    if live_bad["compliant"]:
        return fail("plain-text public-canary recommendation was not flagged")
    live_good = C.check_draft(
        "Open a pull request only. Never a private canary and never a public marketplace.",
        blob,
    )
    if not live_good["compliant"]:
        return fail(f"negated canary/marketplace text flagged {live_good['violations']}")

    if not ART.is_file():
        return fail("catalog artifact missing")
    if "SUCCESS:RES-0183" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel missing from artifact")

    print(
        "flagged_public_canary=True silent_pr_only=True mention_silent=True "
        f"private_flagged={not priv['compliant']} tranche_flagged={not tranche['compliant']}"
    )
    print("SUCCESS:RES-0183-probe1 both-states public-canary vs PR-ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
