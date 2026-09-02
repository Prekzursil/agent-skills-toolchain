#!/usr/bin/env python3
"""Independent recount of CNL-0057 fixtures. Does not read the design note.

Re-derives plurality, mean, and live-set from fixture bytes with stdlib only
(plus the engine's detect() for the planted-vote check). Produces a
counterexample instance; a numeric disagreement with the engine blocks.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import synthesis_only as S  # noqa: E402


def recount_plurality(ballots: list[dict]) -> tuple[str | None, dict[str, int]]:
    counts = Counter(str(b["choice"]) for b in ballots)
    top = counts.most_common(1)[0][1]
    winners = sorted(k for k, n in counts.items() if n == top)
    winner = winners[0] if len(winners) == 1 else None
    return winner, dict(sorted(counts.items()))


def recount_mean(ballots: list[dict]) -> float:
    values = [float(b["value"]) for b in ballots]
    return sum(values) / float(len(values))


def live_set(ballots: list[dict]) -> list[str]:
    keys = []
    for b in ballots:
        keys.append(str(b["value"] if "value" in b else b["choice"]))
    return sorted(set(keys))


def main() -> int:
    diag = S.load_fixture("diagnosis_split.json")
    scalar = S.load_fixture("scalar_estimate.json")
    pref = S.load_fixture("preference_ok.json")
    uni = S.load_fixture("unanimous_diagnosis.json")

    w, tally = recount_plurality(diag["ballots"])
    engine = S.vote(diag)
    print(f"recount_diagnosis winner={w} tally={tally}")
    print(f"engine_diagnosis winner={engine.get('winner')} tally={engine.get('tally')}")
    if w != engine.get("winner") or tally != engine.get("tally"):
        print("FAILED:CNL-0057-reviewer diagnosis recount disagrees with engine")
        return 1

    mean = recount_mean(scalar["ballots"])
    held = {float(b["value"]) for b in scalar["ballots"]}
    ev = S.vote(scalar)
    print(f"recount_scalar mean={mean} held={sorted(held)} mean_in_held={mean in held}")
    if ev.get("manufactured_scalar") != mean:
        print("FAILED:CNL-0057-reviewer scalar mean disagrees with engine")
        return 1
    if mean in held:
        print("FAILED:CNL-0057-reviewer expected manufactured mean absent from held set")
        return 1

    live = live_set(diag["ballots"])
    syn = S.synthesis(diag)
    print(f"recount_live={live} synthesis_live={syn.get('live_hypotheses')} winner={syn.get('winner')}")
    if live != syn.get("live_hypotheses") or syn.get("winner") is not None:
        print("FAILED:CNL-0057-reviewer synthesis live-set disagrees")
        return 1

    # Counterexample instance: unanimous diagnosis. A census number (3) exists.
    # If the claim were "any number from seats is fake", this would refute.
    # The actual claim is that vote-as-decision still manufactures a winner
    # from a census; detect() must still FIRE.
    cx = S.detect(uni)
    print(
        "counterexample id=CX-unanimous-diagnosis-vote attempted=True "
        f"census_unanimous=True detect={cx['output']} refutes={not cx['fires']}"
    )
    if not cx["fires"]:
        print(
            "FAILED:CNL-0057-reviewer unanimous diagnosis vote was silent; "
            "census-as-decision would launder a fact-finding tally"
        )
        return 1

    pref_d = S.detect(pref)
    print(f"preference_vote detect={pref_d['output']} fires={pref_d['fires']}")
    if pref_d["fires"]:
        print("FAILED:CNL-0057-reviewer preference vote false-positive; claim overbroad")
        return 1

    print("reviewer_verdict=PASS independent=True counterexample_attempted=True refutes=False")
    print("SUCCESS:CNL-0057-reviewer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
