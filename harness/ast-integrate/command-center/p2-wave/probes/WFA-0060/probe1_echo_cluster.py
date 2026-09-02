#!/usr/bin/env python3
"""Probe 1: planted echo cluster collapses; frequency ranking would hide the echo.

Both-states:
  GOOD — shared-upstream collapse: 10 artifacts → independent_evidence=1; echo
          loses to deterministic replay on leverage.
  BAD  — treating frequency as evidence: the same cluster outranks replay.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import corpus as C  # noqa: E402
import ranker as R  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0060-mechanism-leverage-ranking.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0060-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0060" not in text:
        return fail("sentinel absent")

    mechs, _upstream = C.mechanisms()
    live = R.rank_mechanisms(mechs)
    echo = live["by_id"][R.ECHO_ID]
    replay = live["by_id"][R.REPLAY_ID]
    fanin = live["by_id"][R.FANIN_ID]
    partial = live["by_id"][R.PARTIAL_ID]

    if echo["frequency"] != 10:
        return fail(f"planted frequency={echo['frequency']} want=10")
    if echo["independent_evidence"] != 1:
        return fail(
            f"planted independent_evidence={echo['independent_evidence']} want=1"
        )
    ups = {c["upstream_id"] for c in echo["independent_sources"]}
    if ups != {"upstream.stale-brief-v1"}:
        return fail(f"planted upstream set {ups}")
    if echo["echo_vs_signal"] != "ECHO" or "ECHO" not in echo["tags"]:
        return fail("planted cluster not tagged ECHO")
    if "SINGLE-SOURCE" not in echo["tags"]:
        return fail("planted cluster missing SINGLE-SOURCE")

    good_echo_loses_to_replay = echo["leverage_score"] < replay["leverage_score"]
    bad_echo_beats_replay = (
        echo["naive_frequency_as_evidence_score"] > replay["leverage_score"]
    )
    if not good_echo_loses_to_replay:
        return fail("GOOD state: collapsed echo still beats replay")
    if not bad_echo_beats_replay:
        return fail("BAD state: frequency-as-evidence did not beat replay")
    if fanin["leverage_rank"] != 1:
        return fail(f"fanin leverage_rank={fanin['leverage_rank']} want=1")
    if echo["frequency_rank"] != 1:
        return fail(f"echo frequency_rank={echo['frequency_rank']} want=1")
    if partial["frequency"] != 3 or partial["independent_evidence"] != 2:
        return fail("partial cluster did not collapse 3 artifacts to 2 sources")

    art_echo = None
    for rec in doc.get("records") or []:
        if rec.get("mechanism_id") == R.ECHO_ID:
            art_echo = rec
            break
    if not art_echo:
        return fail("artifact missing planted echo record")
    if int(art_echo["independent_evidence"]) != 1:
        return fail("artifact independent_evidence != live collapse")
    if int(art_echo["frequency"]) != 10:
        return fail("artifact frequency != 10")
    if not doc.get("frequency_ranking") or not doc.get("leverage_ranking"):
        return fail("artifact suppressed a ranking")
    planted = doc.get("planted_echo_cluster") or {}
    if planted.get("works") is not True:
        return fail("artifact planted_echo_cluster.works is not true")

    payload = {
        "both_states": {
            "bad_frequency_as_evidence_beats_replay": bad_echo_beats_replay,
            "good_collapse_echo_loses_to_replay": good_echo_loses_to_replay,
        },
        "echo": {
            "frequency": echo["frequency"],
            "frequency_rank": echo["frequency_rank"],
            "independent_evidence": echo["independent_evidence"],
            "leverage_rank": echo["leverage_rank"],
            "leverage_score": echo["leverage_score"],
            "naive_score": echo["naive_frequency_as_evidence_score"],
            "tags": echo["tags"],
        },
        "pass": True,
        "probe": "probe1-planted-echo-cluster",
        "unit_id": "WFA-0060",
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"echo_freq={echo['frequency']} independent_n={echo['independent_evidence']} "
        f"lev={echo['leverage_score']} naive={echo['naive_frequency_as_evidence_score']} "
        f"replay_lev={replay['leverage_score']} fanin_rank={fanin['leverage_rank']}"
    )
    print(
        "SUCCESS:WFA-0060-probe1 planted echo collapses 10→1; "
        "frequency-as-evidence is the BAD arm"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
