#!/usr/bin/env python3
"""Probe 1: rule is written (and hashed) before apply; spikes can falsify it.

Both-states:
  A. written_before_apply=True -> apply proceeds; flag False -> apply refused.
  B. live spikes confirm v1; a planted cheaper-path contradiction is detected
     and a revision re-runs every verdict, changing the planted row.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate as G  # noqa: E402

RAW = HERE / "probe1-rule-before-apply.raw.json"
PLANTED_ID = "fx-repair-08-near-keep-queue"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0093-probe1 {msg}")
    return 1


def main() -> int:
    hashed_before = G.rule_hash(G.RULE)
    if not G.RULE.get("written_before_apply"):
        return fail("RULE.written_before_apply is not True before apply")

    unmarked = copy.deepcopy(G.RULE)
    unmarked["written_before_apply"] = False
    refused = False
    try:
        G.apply_rule(G.load_candidates(), rule=unmarked)
    except ValueError as exc:
        refused = "written_before_apply" in str(exc)
    if not refused:
        return fail("apply succeeded without written_before_apply (rule-after-verdict)")

    cands = G.load_candidates()
    spikes = G.load_spikes()
    v1 = G.apply_rule(cands, rule=G.RULE)
    hashes = {d["rule_hash"] for d in v1}
    if hashes != {hashed_before}:
        return fail(f"rule_hash drifted during apply: before={hashed_before} got={hashes}")

    live_hits = G.spike_contradictions(v1, spikes)
    if live_hits:
        return fail(f"live spikes contradict v1 (unexpected on this corpus): {live_hits}")

    near = [d for d in v1 if d["near_threshold"]]
    near_ids = {d["id"] for d in near}
    spike_ids = {s["candidate_id"] for s in spikes}
    if not spike_ids <= near_ids:
        return fail(f"spikes are not near-threshold: spikes={spike_ids} near={near_ids}")

    keep08 = next(d for d in v1 if d["id"] == PLANTED_ID)
    if keep08["disposition"] != "REPAIR":
        return fail(f"planted target {PLANTED_ID} is not a v1 KEEP: {keep08['disposition']}")

    planted_spikes = copy.deepcopy(spikes)
    planted = next(s for s in planted_spikes if s["candidate_id"] == PLANTED_ID)
    planted["rebuild_path_hours"] = 1
    planted["repair_path_hours"] = 5
    planted["cheaper_measured_path"] = "rebuild"
    planted_hits = G.spike_contradictions(v1, planted_spikes)
    if not planted_hits:
        return fail("planted spike contradiction was silent (detector does not fire)")
    if PLANTED_ID not in {h["candidate_id"] for h in planted_hits}:
        return fail(f"planted hit missed {PLANTED_ID}: {planted_hits}")

    revised, meta = G.revise_with_spikes(cands, planted_spikes, rule=G.RULE)
    rev08 = next(d for d in revised if d["id"] == PLANTED_ID)
    if rev08["disposition"] == "REPAIR":
        return fail("revision did not change planted KEEP after rebuild-cheaper spike")
    if len(revised) != 15:
        return fail(f"revision did not re-run all 15 verdicts: {len(revised)}")
    if meta["to_rule"] == G.RULE["id"]:
        return fail("revision kept v1 rule id")

    doc = {
        "written_before_apply": True,
        "apply_refused_without_flag": True,
        "rule_hash_before": hashed_before,
        "rule_hash_on_decisions": sorted(hashes),
        "live_contradictions": live_hits,
        "planted_contradictions": planted_hits,
        "near_threshold_ids": sorted(near_ids),
        "revision_changed_planted": rev08["disposition"] != "REPAIR",
        "revised_disposition_08": rev08["disposition"],
        "v1_histogram": G.histogram(v1),
        "pass": True,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "written_before_apply=True apply_refused_without_flag=True "
        f"live_contradictions=0 planted_fired=True "
        f"v1_{PLANTED_ID}=REPAIR revised={rev08['disposition']} "
        f"rule_hash={hashed_before[:12]}"
    )
    print("SUCCESS:WFA-0093-probe1 rule-before-apply spike-falsifier both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
