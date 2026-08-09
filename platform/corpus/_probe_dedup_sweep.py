"""Threshold sweep for the D3 mechanism-signature dedup predicate.

SELECTION CRITERION (fixed before this sweep was run, see dedup.Thresholds docstring):
    maximise positive-control recall subject to negative-control false-merge rate <= 0.02.

Positive control : 55 authored (canonical <- absorbed) pairs from 07-OPTION-UNIVERSE.md §3,
                   evaluated with D2 (authored absorption) switched OFF.
Negative control : every authored `not a duplicate:` pair, evaluated with the D4 veto OFF.

Emits the FULL sweep so the operating point is auditable rather than cherry-picked.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corpusnorm.dedup import (  # noqa: E402
    Thresholds,
    parse_authored_ledger,
    to_nodes,
    validate,
)
from corpusnorm.extract import extract_corpus  # noqa: E402

CORPUS = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
# SUPERSEDED by _probe_dedup_sweep2.py.  Kept because it records the v1 criterion and the
# measurement that forced the revision.  Writes to its OWN file: pointing both sweeps at
# DEDUP-VALIDATION.json meant a re-run of v1 would silently clobber v2 results.
OUT = Path(__file__).resolve().parent / "DEDUP-VALIDATION-v1-superseded.json"
MAX_FALSE_MERGE_RATE = 0.02


def main() -> int:
    recs = extract_corpus(CORPUS)
    nodes = to_nodes(recs)
    ledger = parse_authored_ledger(CORPUS)
    print(
        f"records={len(recs)} ledger_rows={len(ledger)} absorbed={sum(len(a) for _, a, _ in ledger)}"
    )

    grid = []
    for vj, vo, hj, ho, sj, k in itertools.product(
        (0.30, 0.40, 0.50),
        (2, 3),
        (0.25, 0.34, 0.50),
        (1, 2),
        (0.40, 0.50, 0.60),
        (1, 2, 3),
    ):
        t = Thresholds(
            verb_jaccard_min=vj,
            verb_overlap_min=vo,
            hard_jaccard_min=hj,
            hard_overlap_min=ho,
            soft_jaccard_min=sj,
            locus_top_k=k,
        )
        # locus_top_k is baked into the signature at extraction time, so only k==2 is
        # measurable without re-deriving signatures.  Re-derive per k.
        v = validate(nodes if k == 2 else _renode(recs, k), ledger, t)
        pc, nc = v["positive_control"], v["negative_control"]
        grid.append(
            {
                "thresholds": v["thresholds"],
                "recall": pc["recall"],
                "pos_pairs": pc["pairs"],
                "pos_fired": pc["d3_fired"],
                "false_merge_rate": nc["false_merge_rate"],
                "neg_pairs": nc["pairs"],
                "neg_fired": nc["d3_fired_falsely"],
            }
        )

    admissible = [
        g for g in grid if (g["false_merge_rate"] or 0) <= MAX_FALSE_MERGE_RATE
    ]
    admissible.sort(key=lambda g: (-(g["recall"] or 0), g["false_merge_rate"] or 0))
    print(
        f"\ngrid points={len(grid)}  admissible(fmr<={MAX_FALSE_MERGE_RATE})={len(admissible)}"
    )
    print("\nTOP 12 ADMISSIBLE (recall desc):")
    print(
        f"{'vJ':>5}{'vO':>4}{'hJ':>6}{'hO':>4}{'sJ':>6}{'k':>3} | {'recall':>7} {'fmr':>7} {'negfired':>9}"
    )
    for g in admissible[:12]:
        th = g["thresholds"]
        print(
            f"{th['verb_jaccard_min']:>5}{th['verb_overlap_min']:>4}{th['hard_jaccard_min']:>6}"
            f"{th['hard_overlap_min']:>4}{th['soft_jaccard_min']:>6}{th['locus_top_k']:>3} | "
            f"{g['recall']:>7} {g['false_merge_rate']:>7} {g['neg_fired']:>9}"
        )
    print("\nBEST BY RECALL IGNORING THE CRITERION (for contrast, NOT selected):")
    by_recall = sorted(grid, key=lambda g: -(g["recall"] or 0))[:5]
    for g in by_recall:
        th = g["thresholds"]
        print(
            f"  recall={g['recall']} fmr={g['false_merge_rate']} "
            f"vJ={th['verb_jaccard_min']} sJ={th['soft_jaccard_min']} k={th['locus_top_k']}"
        )

    chosen = admissible[0] if admissible else None
    # detector control: a deliberately impossible operating point must score recall 0
    impossible = Thresholds(
        verb_jaccard_min=1.01,
        verb_overlap_min=99,
        hard_jaccard_min=1.01,
        hard_overlap_min=99,
        soft_jaccard_min=1.01,
        locus_top_k=2,
    )
    vimp = validate(nodes, ledger, impossible)
    control_ok = vimp["positive_control"]["d3_fired"] == 0
    print(
        f"\nDETECTOR CONTROL (impossible thresholds must fire 0): fired="
        f"{vimp['positive_control']['d3_fired']} -> {'PASS' if control_ok else 'FAIL'}"
    )

    # and a trivially-permissive point must fire on nearly everything, proving the harness
    # is capable of reporting a hit at all (both-states discipline)
    permissive = Thresholds(
        verb_jaccard_min=0.0,
        verb_overlap_min=0,
        hard_jaccard_min=0.0,
        hard_overlap_min=0,
        soft_jaccard_min=0.0,
        locus_top_k=3,
    )
    vper = validate(nodes, ledger, permissive)
    perm_ok = (
        vper["positive_control"]["d3_fired"] > vimp["positive_control"]["d3_fired"]
    )
    print(
        f"DETECTOR CONTROL (permissive thresholds must fire many): fired="
        f"{vper['positive_control']['d3_fired']}/{vper['positive_control']['pairs']}"
        f" -> {'PASS' if perm_ok else 'FAIL'}"
    )

    payload = {
        "selection_criterion": (
            "maximise positive-control recall subject to negative-control "
            f"false_merge_rate <= {MAX_FALSE_MERGE_RATE}; fixed before the sweep"
        ),
        "grid_points": len(grid),
        "admissible_points": len(admissible),
        "chosen": chosen,
        "detector_controls": {
            "impossible_thresholds_fire_zero": control_ok,
            "impossible_fired": vimp["positive_control"]["d3_fired"],
            "permissive_thresholds_fire_many": perm_ok,
            "permissive_fired": vper["positive_control"]["d3_fired"],
        },
        "full_grid": grid,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    ok = bool(chosen) and control_ok and perm_ok
    print(("SUCCESS" if ok else "FAILED") + ":dedup-sweep")
    return 0 if ok else 1


def _renode(recs, k: int):
    """Re-derive signatures at a different locus_top_k."""
    from corpusnorm import mechanism as M

    nodes = to_nodes(recs)
    for n, r in zip(nodes, recs, strict=True):
        lt = f"{r.title} . {r.mechanism_text} . {r.problem_text}"
        n.sig = M.Signature(
            verbs=n.sig.verbs,
            locus=n.sig.locus,
            locus_top=M.locus_top_k(lt, k),
            hard=n.sig.hard,
            soft=n.sig.soft,
        )
    return nodes


if __name__ == "__main__":
    raise SystemExit(main())
