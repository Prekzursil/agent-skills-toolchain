"""Sweep v2 -- richness parameters included, THREE controls.

CRITERION REVISION, declared rather than quietly applied
--------------------------------------------------------
Sweep v1 maximised positive-control recall subject to (NEG1 false_merge_rate <= 0.02), where
NEG1 = the 616 authored `not a duplicate:` pairs.  It selected a point that NEG1 scored clean
at 1.62% -- and the resulting build then produced a 15-record cluster justified only by the
shared word "gate".  NEG1 could not see that class: all 616 of its pairs sit in the option
families, which carry rich hand-written mechanism prose, while the failure lives in the
classes with no mechanism field at all.

So the criterion is REVISED, and the reason is a new falsifiable measurement, not taste:

    maximise POS recall  subject to  NEG1 fmr <= 0.02  AND  NEG2 fmr <= 0.002

NEG2 = intra-document declared-distinct pairs (17,399 of them, 28x NEG1, concentrated in the
thin-signature population).  Its bound is TIGHTER than NEG1 because a fire there contradicts a
same-document same-class distinctness declaration directly.  0.002 x 17,399 ~= 35 admitted
merges, each individually listed in the output for audit.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from corpusnorm.controls import intra_document_control  # noqa: E402
from corpusnorm.dedup import (  # noqa: E402
    Thresholds,
    d3_signature_match,
    parse_authored_ledger,
    to_nodes,
    validate,
)
from corpusnorm.extract import extract_corpus  # noqa: E402

CORPUS = Path(r"C:/Users/Prekzursil/.claude/harness-restore-20260806")
OUT = Path(__file__).resolve().parent / "DEDUP-VALIDATION.json"
NEG1_MAX = 0.02
NEG2_MAX = 0.002


def main() -> int:
    recs = extract_corpus(CORPUS)
    nodes = to_nodes(recs)
    ledger = parse_authored_ledger(CORPUS)
    print(f"records={len(recs)} ledger_absorbed={sum(len(a) for _, a, _ in ledger)}")

    grid = []
    combos = list(
        itertools.product(
            (0.40, 0.50),  # verb_jaccard_min
            (0.25, 0.34),  # hard_jaccard_min
            (0.50, 0.60),  # soft_jaccard_min
            (1, 2),  # min_verbs
            (1, 2),  # min_referents
            (2, 3, 4),  # min_soft_referents
            (1, 2),  # min_verb_intersection
            (1, 2),  # min_hard_intersection
            (1, 2, 3),  # min_soft_intersection
        )
    )
    print(f"grid points to evaluate: {len(combos)}")
    for k, (vj, hj, sj, mv, mr, msr, mvi, mhi, msi) in enumerate(combos):
        t = Thresholds(
            verb_jaccard_min=vj,
            verb_overlap_min=3,
            hard_jaccard_min=hj,
            hard_overlap_min=2,
            soft_jaccard_min=sj,
            locus_top_k=2,
            min_verbs=mv,
            min_referents=mr,
            min_soft_referents=msr,
            min_verb_intersection=mvi,
            min_hard_intersection=mhi,
            min_soft_intersection=msi,
        )
        v = validate(nodes, ledger, t)
        n2 = intra_document_control(nodes, d3_signature_match, t)
        grid.append(
            {
                "thresholds": {
                    "verb_jaccard_min": vj,
                    "hard_jaccard_min": hj,
                    "soft_jaccard_min": sj,
                    "min_verbs": mv,
                    "min_referents": mr,
                    "min_soft_referents": msr,
                    "min_verb_intersection": mvi,
                    "min_hard_intersection": mhi,
                    "min_soft_intersection": msi,
                },
                "recall": v["positive_control"]["recall"],
                "pos_fired": v["positive_control"]["d3_fired"],
                "pos_pairs": v["positive_control"]["pairs"],
                "neg1_fmr": v["negative_control"]["false_merge_rate"],
                "neg1_fired": v["negative_control"]["d3_fired_falsely"],
                "neg1_pairs": v["negative_control"]["pairs"],
                "neg2_fmr": n2["false_merge_rate"],
                "neg2_fired": n2["d3_fired_falsely"],
                "neg2_pairs": n2["pairs"],
            }
        )
        if (k + 1) % 48 == 0:
            print(f"  ...{k + 1}/{len(combos)}")

    adm = [
        g
        for g in grid
        if (g["neg1_fmr"] or 0) <= NEG1_MAX and (g["neg2_fmr"] or 0) <= NEG2_MAX
    ]

    def strictness(g):
        th = g["thresholds"]
        return (
            th["min_verbs"]
            + th["min_referents"]
            + th["min_soft_referents"]
            + th["min_verb_intersection"]
            + th["min_hard_intersection"]
            + th["min_soft_intersection"]
            + th["verb_jaccard_min"]
            + th["hard_jaccard_min"]
            + th["soft_jaccard_min"]
        )

    # Tie-break: among equally-performing points prefer the STRICTEST, because a looser point
    # that ties today admits more merges as the corpus grows.  Deterministic.
    adm.sort(
        key=lambda g: (
            -(g["recall"] or 0),
            (g["neg2_fmr"] or 0),
            (g["neg1_fmr"] or 0),
            -strictness(g),
        )
    )
    print(f"\nadmissible: {len(adm)}/{len(grid)}  (neg1<={NEG1_MAX}, neg2<={NEG2_MAX})")
    print("\nTOP 10 ADMISSIBLE:")
    print(f"{'recall':>7}{'n1':>5}{'n2':>5} | vJ  hJ  sJ  mv mr msr mvi mhi msi")
    for g in adm[:10]:
        th = g["thresholds"]
        print(
            f"{g['recall']:>7}{g['neg1_fired']:>5}{g['neg2_fired']:>5} | "
            f"{th['verb_jaccard_min']} {th['hard_jaccard_min']} {th['soft_jaccard_min']} "
            f"{th['min_verbs']}  {th['min_referents']}  {th['min_soft_referents']}   "
            f"{th['min_verb_intersection']}   {th['min_hard_intersection']}   "
            f"{th['min_soft_intersection']}"
        )
    print("\nFOR CONTRAST -- best recall ignoring BOTH ceilings (NOT selected):")
    for g in sorted(grid, key=lambda g: -(g["recall"] or 0))[:3]:
        print(
            f"  recall={g['recall']} neg1_fired={g['neg1_fired']} neg2_fired={g['neg2_fired']}"
        )

    chosen = adm[0] if adm else None

    # detector controls, both states
    imp = Thresholds(verb_jaccard_min=1.01, min_verbs=99, min_verb_intersection=99)
    per = Thresholds(
        verb_jaccard_min=0.0,
        verb_overlap_min=0,
        hard_jaccard_min=0.0,
        hard_overlap_min=0,
        soft_jaccard_min=0.0,
        locus_top_k=3,
        min_verbs=0,
        min_referents=0,
        min_soft_referents=0,
        min_verb_intersection=0,
        min_hard_intersection=0,
        min_soft_intersection=0,
    )
    vi = validate(nodes, ledger, imp)["positive_control"]["d3_fired"]
    vp = validate(nodes, ledger, per)["positive_control"]["d3_fired"]
    print(
        f"\nDETECTOR CONTROL impossible-> fired={vi} (must be 0): {'PASS' if vi == 0 else 'FAIL'}"
    )
    print(
        f"DETECTOR CONTROL permissive -> fired={vp}/55 (must be >0): {'PASS' if vp > vi else 'FAIL'}"
    )

    payload = {
        "criterion": (
            f"maximise positive-control recall subject to NEG1 fmr <= {NEG1_MAX} AND "
            f"NEG2 fmr <= {NEG2_MAX}"
        ),
        "criterion_revision_reason": (
            "sweep v1 constrained only NEG1 (616 authored not-a-duplicate pairs, all inside the "
            "option families). It scored the selected point clean at 1.62% while the build it "
            "produced merged 15 records on the single shared word 'gate'. NEG2 (17,399 "
            "intra-document declared-distinct pairs) covers that thin-signature population. "
            "The criterion was revised because a new control measured a failure the old one "
            "structurally could not see."
        ),
        "grid_points": len(grid),
        "admissible_points": len(adm),
        "chosen": chosen,
        "top_admissible": adm[:10],
        "best_recall_unconstrained": sorted(grid, key=lambda g: -(g["recall"] or 0))[
            :3
        ],
        "detector_controls": {
            "impossible_fired": vi,
            "permissive_fired": vp,
            "impossible_fires_zero": vi == 0,
            "permissive_fires_more": vp > vi,
        },
        "full_grid": grid,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nwrote {OUT}")
    ok = bool(chosen) and vi == 0 and vp > vi
    print(("SUCCESS" if ok else "FAILED") + ":dedup-sweep2")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
