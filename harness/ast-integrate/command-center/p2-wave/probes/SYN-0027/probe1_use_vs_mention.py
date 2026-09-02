#!/usr/bin/env python3
"""Probe 1: use-vs-mention control + unmodified lens identity.

A lens document quoting 'every unit passes' must not self-flag as a USE
defect. The wrapper-disabled substring matcher must still fire (both-states).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE / "lenses"))

from runner import (  # noqa: E402
    QUOTE_PHRASE,
    artifact_field,
    labels_ok,
    run,
    use_vs_mention_control,
)

ART = REPO / "command-center/receipts/SYN-0027.json"


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0027-probe1 {msg}")
    return 1


def main() -> int:
    uvm = use_vs_mention_control()
    bundle = run()
    payload = {
        "probe": "probe1-use-vs-mention",
        "unit_id": "SYN-0027",
        "quoted_phrase": QUOTE_PHRASE,
        "role_on_quoted_span": uvm["role_on_quoted_span"],
        "substring_matcher_role": uvm["substring_matcher_role"],
        "self_flagged_as_use_defect": uvm["self_flagged_as_use_defect"],
        "both_states_discriminate": uvm["both_states_discriminate"],
        "lens_byte_identical": bundle["lens_identity"]["byte_identical"],
        "every_finding_labeled": bundle["every_finding_labeled"],
        "mention_never_counted_as_defect": bundle["mention_never_counted_as_defect"],
    }
    if uvm["role_on_quoted_span"] != "MENTION":
        return fail(f"quoted span role={uvm['role_on_quoted_span']}")
    if uvm["substring_matcher_role"] != "USE":
        return fail("substring matcher did not treat quoted phrase as USE")
    if not uvm["both_states_discriminate"]:
        return fail("both-states silent: role matcher and substring matcher agree")
    if uvm["self_flagged_as_use_defect"] or not uvm["passed"]:
        return fail(f"quoted phrase self-flagged {uvm['finding_ids_if_self_flagged']}")
    if not bundle["lens_identity"]["byte_identical"]:
        return fail(f"lens identity {bundle['lens_identity']['mismatches']}")
    labeled, mention_ok = labels_ok(bundle["findings"])
    if not labeled:
        return fail("a finding is missing USE|MENTION")
    if not mention_ok:
        return fail("a MENTION finding was counted as a defect")

    mention_hits = [
        f
        for f in bundle["findings"]
        if f.get("use_or_mention") == "MENTION"
        and QUOTE_PHRASE in (str(f.get("sentence") or "") + str(f.get("span") or "")).lower()
    ]
    if not mention_hits:
        return fail("quoted phrase produced no MENTION finding (discriminator did not run)")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        uvm_art = artifact_field(doc, "use_vs_mention_control") or {}
        ident_art = artifact_field(doc, "lens_identity") or {}
        findings_art = artifact_field(doc, "findings") or []
        if not isinstance(uvm_art, dict) or uvm_art.get("passed") is not True:
            return fail("artifact use_vs_mention_control.passed is not true")
        if artifact_field(doc, "every_finding_labeled") is not True:
            return fail("artifact every_finding_labeled is not true")
        if artifact_field(doc, "mention_never_counted_as_defect") is not True:
            return fail("artifact mention_never_counted_as_defect is not true")
        if not isinstance(ident_art, dict) or ident_art.get("byte_identical") is not True:
            return fail("artifact lens_identity.byte_identical is not true")
        if not isinstance(findings_art, list):
            return fail("artifact findings is not a list")
        for row in findings_art:
            if not isinstance(row, dict):
                return fail("artifact finding row is not an object")
            if row.get("use_or_mention") not in {"USE", "MENTION"}:
                return fail(f"artifact finding {row.get('id')} unlabeled")
            if row.get("use_or_mention") == "MENTION" and row.get("counted_as_defect"):
                return fail(f"artifact MENTION {row.get('id')} counted as defect")

    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:SYN-0027-probe1 quoting 'every unit passes' is MENTION not a USE defect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
