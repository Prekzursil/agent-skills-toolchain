#!/usr/bin/env python3
"""Probe 2: independent recount from fixture JSON (set algebra + ballot sums).

Does not read the author's artifact for the numbers. A disagreement with
evaluate.run_council blocks the unit. Records the negative control verbatim.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from evaluate import run_council
from fixtures import fire, silent_low_consensus, silent_new_objection
from identity import admissible, same_objection, slot_key


def _consensus(ballots: list[dict]) -> float:
    support = 0.0
    oppose = 0.0
    for b in ballots:
        w = float(b.get("weight") or 1.0)
        vote = str(b.get("vote") or "silent").lower()
        if vote in {"support", "aye", "yes"}:
            support += w
        elif vote in {"oppose", "nay", "no"}:
            oppose += w
    denom = support + oppose
    return (support / denom) if denom else 0.0


def recount(fixture: dict) -> dict:
    """Mechanically different from evaluate.py: set of slot keys, not object list."""
    seen: set[tuple[str, str, str]] = set()
    quiet = 0
    rows = []
    stop = False
    for rnd in fixture["rounds"]:
        admitted = [o for o in (rnd.get("objections") or []) if admissible(o)]
        new_slots = []
        for obj in admitted:
            key = slot_key(obj)
            if key not in seen:
                new_slots.append(key)
        if new_slots:
            quiet = 0
            seen.update(new_slots)
        else:
            quiet += 1
        consensus = _consensus(list(rnd.get("ballots") or []))
        stop = consensus >= 0.95 and quiet >= 2
        rows.append(
            {
                "round": rnd["round"],
                "consensus": consensus,
                "no_new_objection_rounds": quiet,
                "new_slot_count": len(new_slots),
                "stop": stop,
                "newly_recruited": list(rnd.get("newly_recruited") or rnd.get("newly_recruited") or []),
            }
        )
    return {
        "fixture_id": fixture.get("id"),
        "stop": stop,
        "final_consensus": rows[-1]["consensus"] if rows else 0.0,
        "final_quiet": rows[-1]["no_new_objection_rounds"] if rows else 0,
        "rounds": rows,
    }


def _agree(author: dict, review: dict, label: str) -> list[str]:
    errs: list[str] = []
    if bool(author["stop"]) != bool(review["stop"]):
        errs.append(f"{label} stop author={author['stop']} review={review['stop']}")
    a_q = int(author["final"]["no_new_objection_rounds"])
    if a_q != int(review["final_quiet"]):
        errs.append(f"{label} quiet author={a_q} review={review['final_quiet']}")
    a_c = float(author["final"]["consensus"])
    if abs(a_c - float(review["final_consensus"])) > 1e-12:
        errs.append(f"{label} consensus author={a_c} review={review['final_consensus']}")
    if len(author["rounds"]) != len(review["rounds"]):
        errs.append(f"{label} round count mismatch")
        return errs
    for ar, rr in zip(author["rounds"], review["rounds"]):
        if int(ar["new_count"]) != int(rr["new_slot_count"]):
            errs.append(
                f"{label} r{ar['round']} new_count author={ar['new_count']} review={rr['new_slot_count']}"
            )
        if abs(float(ar["consensus"]) - float(rr["consensus"])) > 1e-12:
            errs.append(f"{label} r{ar['round']} consensus mismatch")
        if int(ar["no_new_objection_rounds"]) != int(rr["no_new_objection_rounds"]):
            errs.append(f"{label} r{ar['round']} quiet mismatch")
        if bool(ar["stop"]) != bool(rr["stop"]):
            errs.append(f"{label} r{ar['round']} stop mismatch")
    return errs


def main() -> int:
    cases = [
        ("fire", fire()),
        ("silent_new_objection", silent_new_objection()),
        ("silent_low_consensus", silent_low_consensus()),
    ]
    errors: list[str] = []
    reviews = {}
    for label, fx in cases:
        author = run_council(fx)
        review = recount(fx)
        reviews[label] = review
        print(
            f"recount[{label}] "
            + json.dumps(
                {k: review[k] for k in ("stop", "final_consensus", "final_quiet")},
                sort_keys=True,
            )
        )
        errors.extend(_agree(author, review, label))

        first_admitted = None
        for rnd in fx["rounds"]:
            for obj in rnd.get("objections") or []:
                if not admissible(obj):
                    continue
                if first_admitted is None:
                    first_admitted = obj
                    continue
                if slot_key(obj) == slot_key(first_admitted):
                    if not same_objection(obj, first_admitted):
                        errors.append(f"{label} slot match but same_objection False")

    if errors:
        for e in errors:
            print(f"FAILED:CNL-0079-probe2 {e}")
        return 1

    reset = reviews["silent_new_objection"]
    neg = (
        "NEGATIVE_CONTROL verbatim: on fixture silent-new-objection-from-new-recruit-resets "
        "the check is meant to REJECT a stop. Observed: stop={stop} "
        "no_new_objection_rounds={q} consensus={c:.4f} after round 3 "
        "(new defect_class missing-cost-term from newly recruited R-new reset the counter). "
        "The rejected state is 'fire the stop while a genuinely new objection just arrived'."
    ).format(
        stop=reset["stop"],
        q=reset["final_quiet"],
        c=reset["final_consensus"],
    )
    print(neg)
    if reset["stop"] is not False or int(reset["final_quiet"]) != 0:
        print("FAILED:CNL-0079-probe2 negative control did not reject")
        return 1

    fire_r = reviews["fire"]
    if fire_r["stop"] is not True or int(fire_r["final_quiet"]) != 2:
        print("FAILED:CNL-0079-probe2 fire recount numbers")
        return 1

    print("SUCCESS:CNL-0079-probe2 independent-recount negative-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
