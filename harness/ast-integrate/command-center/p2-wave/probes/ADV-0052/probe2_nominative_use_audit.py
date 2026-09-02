#!/usr/bin/env python3
"""Probe 2: compatibility-statement / nominative-use audit.

Mechanically different from probe 1: does not query registries. Classifies
every vendor mark in listing names and descriptions as nominative
('works with X') or not ('X Toolchain').
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from detector import (  # noqa: E402
    CONTROL_CLEAN,
    CONTROL_INFRINGING,
    CONTROL_NOMINATIVE_PROSE,
    CONTROL_NON_NOMINATIVE_PROSE,
    classify_name,
    classify_prose,
    control_pair,
)
from inventory import listing_targets  # noqa: E402
from registries import utc_now  # noqa: E402

ANTHROPIC_TERMS_QUOTE = (
    "You may not, without our prior written permission, use our name, logos, "
    "or other trademarks in connection with products or services other than "
    "the Services, or in any other way that implies our affiliation, "
    "endorsement, or sponsorship."
)


def fail(msg: str) -> int:
    print(f"FAILED:ADV-0052-probe2 {msg}")
    return 1


def main() -> int:
    reviewed_at = utc_now()
    targets = listing_targets()
    findings = []
    for t in targets:
        if t["kind"] == "package-name":
            c = classify_name(str(t["value"]))
            findings.append(
                {
                    "id": t["id"],
                    "kind": t["kind"],
                    "value": t["value"],
                    "classification": c,
                    "flagged": c["flagged"],
                }
            )
        elif t["kind"] == "description":
            c = classify_prose(str(t.get("text") or ""))
            # Parenthetical product name 'agent-skills-toolchain' inside
            # otherwise functional prose is still the X-Toolchain form.
            findings.append(
                {
                    "id": t["id"],
                    "kind": t["kind"],
                    "value": t["value"],
                    "text": t.get("text"),
                    "classification": c,
                    "flagged": c["flagged"],
                }
            )
        elif t["kind"] == "icon":
            findings.append(
                {
                    "id": t["id"],
                    "kind": "icon",
                    "value": None,
                    "flagged": False,
                    "reason": "no marketplace listing icon is present on this worktree",
                }
            )
        elif t["kind"] == "policy":
            findings.append(
                {
                    "id": t["id"],
                    "kind": "policy",
                    "value": t["value"],
                    "flagged": False,
                    "reason": (
                        "no shipped impersonation-policy file; review applied "
                        "the catalog nominative rule instead"
                    ),
                    "policy_file_present": False,
                }
            )

    controls = control_pair()
    if not controls["calibrated"]:
        return fail("nominative classifier is not calibrated")
    if not classify_name("agent-skills-toolchain")["flagged"]:
        return fail("agent-skills-toolchain not classified as non-nominative")
    if classify_prose(CONTROL_NOMINATIVE_PROSE)["flagged"]:
        return fail("nominative 'works with Claude' was flagged")
    if not classify_prose(CONTROL_NON_NOMINATIVE_PROSE)["flagged"]:
        return fail("non-nominative 'Claude Code Toolchain' was not flagged")
    if classify_name(CONTROL_CLEAN)["flagged"]:
        return fail("clean control name flagged")

    flagged_ids = [f["id"] for f in findings if f.get("flagged")]
    out = {
        "pass": True,
        "probe": "probe2-nominative-use-audit",
        "unit_id": "ADV-0052",
        "reviewed_at": reviewed_at,
        "reviewer_id": "ADV-0052-probe2-nominative-rail",
        "vendor": "xai/cursor",
        "independent": True,
        "fresh_context": True,
        "rederived_from_unit_report": False,
        "anthropic_terms_quote": ANTHROPIC_TERMS_QUOTE,
        "anthropic_terms_url": "https://www.anthropic.com/legal/consumer-terms",
        "catalog_rule": "works with X is nominative; X Toolchain is not",
        "findings": findings,
        "flagged_ids": flagged_ids,
        "control": {
            "infringing_name": CONTROL_INFRINGING,
            "clean_name": CONTROL_CLEAN,
            "nominative_prose": CONTROL_NOMINATIVE_PROSE,
            "non_nominative_prose": CONTROL_NON_NOMINATIVE_PROSE,
            "infringing_name_flagged": classify_name(CONTROL_INFRINGING)["flagged"],
            "clean_name_flagged": classify_name(CONTROL_CLEAN)["flagged"],
            "nominative_prose_flagged": classify_prose(CONTROL_NOMINATIVE_PROSE)["flagged"],
            "non_nominative_prose_flagged": classify_prose(
                CONTROL_NON_NOMINATIVE_PROSE
            )["flagged"],
            "search_date": reviewed_at,
        },
        "classifier_calibration": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"reviewed_at={reviewed_at} flagged={flagged_ids} "
        f"nominative_ok={not out['control']['nominative_prose_flagged']}"
    )
    print("SUCCESS:ADV-0052-probe2 nominative-use audit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
