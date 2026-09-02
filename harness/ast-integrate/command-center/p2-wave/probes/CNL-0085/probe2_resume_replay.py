#!/usr/bin/env python3
"""Probe 2: a resumed council replays to the same state up to the intervention.

Mechanism: sha256 of the canonical event prefix plus equality of derived views
(votes, minority reports, round_index) rebuilt from the log. Does not consult
the CONTINUE/RESTART classifier used by probe 1.

Negative control (verbatim): a pause snapshot whose prefix bytes were mutated
(the minority_report text) no longer hashes to prefix_sha256, so from_snapshot
raises PrefixMismatch. That is the tampered pause-record state the check is
meant to reject. A second leg recomputes the hash to match the tampered prefix
and shows the rebuilt minority report diverges from the original, proving the
replay is from events, not a cached dissent string.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from intervention import (  # noqa: E402
    PrefixMismatch,
    CouncilRun,
    apply_intervention,
    hash_prefix,
    replay_to_intervention,
    sha256_obj,
)
from scenario import DISSENT, OPS, scripted_run  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0085-probe2 {msg}")
    return 1


def main() -> int:
    run = scripted_run()
    original_derived = run.derived_state()
    original_hash = run.prefix_sha256()
    original_dissent = list(run.minority_reports)
    snap = run.pause()

    replayed = replay_to_intervention(snap)
    if replayed != original_derived:
        return fail("uninterrupted pause/replay derived state diverged")
    resumed = CouncilRun.from_snapshot(snap)
    if resumed.prefix_sha256() != original_hash:
        return fail("resumed prefix hash diverged")
    if resumed.minority_reports != original_dissent:
        return fail("dissent lost on resume")
    if sha256_obj(resumed.derived_state()) != sha256_obj(original_derived):
        return fail("derived-state sha256 diverged (second instrument)")

    # CONTINUE evidence_add: prefix up to cursor stays byte-identical.
    continued = CouncilRun.from_snapshot(copy.deepcopy(snap))
    cursor = snap["cursor"]
    result = apply_intervention(continued, OPS["evidence_add"])
    if result["applied"] != "CONTINUE":
        return fail("evidence_add on resume did not CONTINUE")
    if hash_prefix(continued.events[:cursor]) != original_hash:
        return fail("intervention mutated prefix before cursor")
    if continued.minority_reports != original_dissent:
        return fail("evidence_add lost dissent")
    if continued.derived_state()["votes"] != original_derived["votes"]:
        return fail("evidence_add rewrote votes")

    # Negative control A: tampered prefix, stale hash.
    tampered = copy.deepcopy(snap)
    for ev in tampered["prefix"]:
        if ev.get("type") == "minority_report":
            ev["text"] = "dissent-dropped-on-purpose"
            break
    else:
        return fail("fixture has no minority_report to tamper")
    mismatch = False
    mismatch_msg = ""
    try:
        CouncilRun.from_snapshot(tampered)
    except PrefixMismatch as exc:
        mismatch = True
        mismatch_msg = str(exc)
    else:
        return fail("tampered pause record with stale hash was accepted")

    # Negative control B: tampered prefix with hash recomputed to match.
    # Replay must NOT produce the original dissent (events are load-bearing).
    rehashed = copy.deepcopy(tampered)
    rehashed["prefix_sha256"] = hash_prefix(rehashed["prefix"])
    rebuilt = CouncilRun.from_snapshot(rehashed)
    if DISSENT in rebuilt.minority_reports:
        return fail("rehashed tampered prefix still produced original dissent (cached?)")
    if rebuilt.minority_reports == original_dissent:
        return fail("tampered events did not change derived dissent")

    out = {
        "probe": "probe2-resume-replay",
        "unit_id": "CNL-0085",
        "pass": True,
        "original_prefix_sha256": original_hash,
        "replay_derived_equal": True,
        "dissent_survived_resume": True,
        "evidence_add_prefix_preserved": True,
        "derived_state_sha256": sha256_obj(original_derived),
        "negative_control": {
            "id": "tampered-pause-record",
            "state_meant_to_reject": (
                "pause snapshot whose minority_report text was mutated so "
                "prefix bytes no longer match prefix_sha256"
            ),
            "what_the_check_does": (
                "CouncilRun.from_snapshot raises PrefixMismatch on a stale "
                "prefix_sha256 (integrity). When the hash is recomputed to match "
                "the tampered bytes, rebuilt minority_reports diverge from the "
                "original dissent, proving replay reads events not a cached string."
            ),
            "fired": mismatch,
            "verbatim_exception": mismatch_msg,
            "rehashed_dissent_diverged": True,
        },
    }
    print(json.dumps(out, sort_keys=True, ensure_ascii=True))
    print(
        f"replay_equal=True prefix={original_hash[:16]}... "
        f"dissent_survived=True tampered_stale_hash_rejected={mismatch}"
    )
    print(f"NEGATIVE CONTROL PrefixMismatch: {mismatch_msg}")
    print("SUCCESS:CNL-0085-probe2 resume replays to the same state up to intervention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
