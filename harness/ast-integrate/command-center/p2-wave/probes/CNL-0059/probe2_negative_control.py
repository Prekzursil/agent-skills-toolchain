#!/usr/bin/env python3
"""Probe 2: independent both-states re-run, negative control, wall-clock distractor.

Reviewer path: load named JSON from disk and call detector.evaluate directly.
Does not read probe1 output. Records verbatim what the check does on the
sycophantic state it is meant to reject.

Second mechanism (not token-Jaccard): difflib.SequenceMatcher pairwise ratio
must still rank the sycophantic named fixture above the obvious one.

Wall-clock mutation: elapsed_ms must not change the verdict.
"""
from __future__ import annotations

import copy
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import overclaim as O  # noqa: E402
import schema_local as S  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def mean_seq_ratio(transcript: dict) -> float:
    seats = (transcript.get("rounds") or [{}])[0].get("seats") or []
    briefs = [str(s.get("brief") or "") for s in seats]
    xs: list[float] = []
    for i in range(len(briefs)):
        for j in range(i + 1, len(briefs)):
            xs.append(
                SequenceMatcher(None, briefs[i].lower(), briefs[j].lower()).ratio()
            )
    return sum(xs) / len(xs) if xs else 0.0


def mutate_elapsed(transcript: dict, ms: int) -> dict:
    t = copy.deepcopy(transcript)
    t["elapsed_ms"] = ms
    return t


def main() -> int:
    F.dump_named()
    good = F.load_named(F.NAMED_OBVIOUS)["transcript"]
    bad = F.load_named(F.NAMED_SYCOPHANTIC)["transcript"]
    g = D.evaluate(good)
    b = D.evaluate(bad)
    print("reviewer_named_obvious " + D.verbatim_line(g))
    print("reviewer_named_sycophantic " + D.verbatim_line(b))
    print("NEGATIVE_CONTROL_VERBATIM " + D.verbatim_line(b))
    if g.get("fire") or not b.get("fire"):
        print("FAILED:CNL-0059-probe2 both-states did not discriminate")
        return 1
    if b.get("remediation") != "blind_re_evaluation":
        print("FAILED:CNL-0059-probe2 reject-state did not contract re-evaluation")
        return 1

    g_fast = D.evaluate(mutate_elapsed(good, 1))
    g_slow = D.evaluate(mutate_elapsed(good, 10**9))
    b_fast = D.evaluate(mutate_elapsed(bad, 1))
    b_slow = D.evaluate(mutate_elapsed(bad, 10**9))
    wall_ok = (
        g_fast.get("fire") is False
        and g_slow.get("fire") is False
        and b_fast.get("fire") is True
        and b_slow.get("fire") is True
    )
    print(
        f"wall_clock_ignored fast_obvious_fire={g_fast.get('fire')} "
        f"slow_obvious_fire={g_slow.get('fire')} "
        f"fast_syc_fire={b_fast.get('fire')} slow_syc_fire={b_slow.get('fire')} "
        f"ok={wall_ok}"
    )
    if not wall_ok:
        print("FAILED:CNL-0059-probe2 elapsed_ms changed the verdict")
        return 1

    seq_g = mean_seq_ratio(good)
    seq_b = mean_seq_ratio(bad)
    print(f"seqratio_obvious={seq_g:.6f} seqratio_sycophantic={seq_b:.6f}")
    if not (seq_b > seq_g):
        print("FAILED:CNL-0059-probe2 SequenceMatcher ranking did not separate")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0059-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    ok, why = O.check_overclaim(doc)
    print(f"overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNL-0059-probe2 overclaim")
        return 1
    body = O.payload(doc)
    nc = body.get("negative_control") or doc.get("negative_control") or {}
    if "fire=True" not in str(nc.get("verbatim") or ""):
        print("FAILED:CNL-0059-probe2 negative_control.verbatim missing fire=True")
        return 1
    rev = body.get("reviewer") or {}
    top_rev = doc.get("reviewer") or {}
    executed = rev.get("executed_both_states")
    if executed is not True:
        notes = str(top_rev.get("notes") or "").lower()
        executed = "both-states" in notes and top_rev.get("independent") is True
    if executed is not True:
        print("FAILED:CNL-0059-probe2 reviewer did not execute both-states")
        return 1

    validator = S.validator()
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNL-0059-probe2 schema errors")
        for e in errs[:8]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = [
        {},
        {"unit_id": "CNL-0059", "false_positive_rate": "low"},
        {"passing_tests": 999999},
    ]
    for gdoc in garbage:
        if not list(validator.iter_errors(gdoc)):
            print(f"FAILED:CNL-0059-probe2 schema accepted garbage {list(gdoc)[:2]}")
            return 1
    print("SUCCESS:CNL-0059-probe2 negative-control wall-clock reviewer-rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
