#!/usr/bin/env python3
"""Probe 1: enforced vs stripped action logs diverge; vote block is at runtime."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenario as S  # noqa: E402

OUT = REPO / "command-center/confirmation/CNF-0090-role-enforcement.json"
SENTINEL = (
    "SUCCESS:CNF-0090 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both configurations ran "
    "and their per-participant action logs are attached and measurably different. "
    "Any other terminal state is FAILED:CNF-0090 <classification> with the "
    "diagnostic tail attached."
)


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0090-probe1 {msg}")
    return 1


def main() -> int:
    live = S.run_cnf_0090()
    comparison = live["comparison"]
    if not comparison["measurably_different"]:
        return fail("role-collapse: enforced and stripped fingerprints match")
    if comparison["delta_accepted_votes"] < 1:
        return fail("vote-rights not visible in accepted-count delta")
    if comparison["delta_accepted_vetoes"] < 1:
        return fail("veto-rights not visible in accepted-count delta")
    if not S.vote_blocked_at_runtime(live["enforced"]):
        return fail("proposer vote was not blocked at runtime")
    if not S.mention_is_not_a_vote(live["enforced"]):
        return fail("mention of vote was classified as a vote")
    proposer = S.event_for(live["enforced"], "alice-proposer", "vote")
    if not proposer or proposer["accepted"] or proposer["enforced_at"] != "runtime":
        return fail("vote refusal is not a runtime enforcement event")

    if not OUT.is_file() or OUT.stat().st_size < 200:
        return fail("confirmation artifact missing")
    raw = OUT.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("catalog sentinel absent from artifact")
    doc = json.loads(raw)
    if doc.get("state") != "SUCCESS":
        return fail(f"artifact state={doc.get('state')}")
    if doc.get("unit_id") != "CNF-0090":
        return fail("unit_id mismatch")
    configs = S.artifact_field(doc, "configurations") or []
    if len(configs) < 2:
        return fail("need two configurations")
    if not all(c.get("ran") for c in configs):
        return fail("a configuration did not run")
    if not all(c.get("participant_action_logs") for c in configs):
        return fail("participant action logs missing")
    cmp_doc = S.artifact_field(doc, "comparison") or {}
    if not cmp_doc.get("measurably_different"):
        return fail("artifact comparison not measurably_different")
    if cmp_doc.get("enforced_fingerprint") != comparison["enforced_fingerprint"]:
        return fail("enforced fingerprint drifted from live re-run")
    if cmp_doc.get("stripped_fingerprint") != comparison["stripped_fingerprint"]:
        return fail("stripped fingerprint drifted from live re-run")

    out = {
        "probe": "probe1-action-log-divergence",
        "unit_id": "CNF-0090",
        "measurably_different": True,
        "delta_accepted_votes": comparison["delta_accepted_votes"],
        "delta_accepted_vetoes": comparison["delta_accepted_vetoes"],
        "delta_accepted_speaks": comparison["delta_accepted_speaks"],
        "vote_blocked_at_runtime": True,
        "mention_is_not_a_vote": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0090-probe1 action-log divergence and runtime vote block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
