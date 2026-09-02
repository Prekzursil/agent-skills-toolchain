#!/usr/bin/env python3
"""Probe 1: summary-only confirmation is rejected (both-states).

Bad: a confirmation that cites only the author's summary is REJECTED and
certify() does not emit CERTIFIED.
Good: a confirmation that cites existing raw per-case rows, from a confirmer
who is not the author, is ACCEPTED and certify() emits CERTIFIED.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from certify import STAGES_HOOK, certify  # noqa: E402
from confirm_hook import (  # noqa: E402
    REASON_NOT_INDEPENDENT,
    REASON_SUMMARY_ONLY,
    VERDICT_ACCEPT,
    VERDICT_REJECT,
    admit,
    load_json,
)

FIX = HERE / "fixtures"


def main() -> int:
    workflow = load_json(FIX / "workflow.json")
    summary = load_json(FIX / "confirmation_summary_only.json")
    citing = load_json(FIX / "confirmation_citing.json")
    same = load_json(FIX / "confirmation_same_author.json")

    bad = admit(summary, workflow, FIX)
    good = admit(citing, workflow, FIX)
    author = admit(same, workflow, FIX)

    cert_bad = certify(workflow, summary, FIX)
    cert_good = certify(workflow, citing, FIX)

    summary_rejected = (
        bad.verdict == VERDICT_REJECT
        and bad.reason == REASON_SUMMARY_ONLY
        and not bad.accepted
        and not cert_bad.get("certified")
        and cert_bad.get("blocked_by") == STAGES_HOOK
        and cert_bad.get("status") == "REJECTED"
        and not bad.digest_accepted
    )
    citing_accepted = (
        good.verdict == VERDICT_ACCEPT
        and good.accepted
        and good.independent
        and good.raw_citations == ["raw/per_case_rows.json"]
        and good.recomputed == {"n": 8, "mean_delta": 0.25, "verdict": "OUTPERFORMS"}
        and cert_good.get("certified") is True
        and cert_good.get("status") == "CERTIFIED"
        and STAGES_HOOK in (cert_good.get("stages_run") or [])
        and cert_good.get("digest_accepted") is False
    )
    same_author_rejected = (
        author.verdict == VERDICT_REJECT
        and author.reason == REASON_NOT_INDEPENDENT
        and not author.independent
    )
    both_states = summary_rejected and citing_accepted

    print(
        json.dumps(
            {
                "probe": "probe1-summary-only-both-states",
                "unit_id": "IMP-0202",
                "summary_only": {
                    "verdict": bad.verdict,
                    "reason": bad.reason,
                    "certified": cert_bad.get("certified"),
                    "blocked_by": cert_bad.get("blocked_by"),
                    "digest_accepted": bad.digest_accepted,
                },
                "artifact_citing": {
                    "verdict": good.verdict,
                    "reason": good.reason,
                    "certified": cert_good.get("certified"),
                    "recomputed": good.recomputed,
                    "raw_citations": good.raw_citations,
                },
                "same_author": {
                    "verdict": author.verdict,
                    "reason": author.reason,
                    "independent": author.independent,
                },
                "summary_rejected": summary_rejected,
                "citing_accepted": citing_accepted,
                "same_author_rejected": same_author_rejected,
                "both_states": both_states,
                "pass": both_states and same_author_rejected,
            },
            indent=2,
            sort_keys=True,
        )
    )
    print(
        f"summary_rejected={summary_rejected} citing_accepted={citing_accepted} "
        f"same_author_rejected={same_author_rejected} both_states={both_states}"
    )
    if not (both_states and same_author_rejected):
        print("FAILED:IMP-0202-probe1 summary-only both-states did not discriminate")
        return 1
    print("SUCCESS:IMP-0202-probe1 summary-only confirmation rejected (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
