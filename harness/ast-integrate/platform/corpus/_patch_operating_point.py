"""Set the swept operating point + add the deterministic tie-break to sweep v2.

Sweep v2 produced a 10-way TIE at recall=0.2545 / NEG1=11 / NEG2=12.  Tie-break rule, stated:
among equally-performing points prefer the STRICTEST (largest richness and intersection
floors), because a stricter point is more robust to corpus growth -- a looser point that ties
today buys nothing and admits more merges as records are added.
"""

import pathlib

here = pathlib.Path(__file__).resolve().parent

# ---- 1. dedup.py defaults -------------------------------------------------------------
p = here / "corpusnorm" / "dedup.py"
s = p.read_text(encoding="utf-8")

A = """    # The swept operating point.  recall=0.2364 at false_merge_rate=0.0162; it is the
    # recall-maximising point of the 22 admissible grid points out of 324 measured.
    verb_jaccard_min: float = 0.50
    verb_overlap_min: int = 3
    hard_jaccard_min: float = 0.25
    hard_overlap_min: int = 2
    soft_jaccard_min: float = 0.60
    locus_top_k: int = 2
"""
B = """    # THE SWEPT OPERATING POINT (sweep v2, 1152 grid points, 1048 admissible).
    #   POS recall = 0.2545 (14/55)
    #   NEG1 false-merge = 11/616   = 0.0179   (authored not-a-duplicate pairs)
    #   NEG2 false-merge = 12/17399 = 0.00069  (intra-document declared-distinct pairs)
    # Chosen by: maximise recall s.t. NEG1 <= 0.02 AND NEG2 <= 0.002; ties broken toward the
    # STRICTEST point, because a looser point that ties today admits more merges as the corpus
    # grows.  Unconstrained recall ceiling was 0.3091 at NEG1=23/NEG2=26 -- rejected.
    verb_jaccard_min: float = 0.50
    verb_overlap_min: int = 3
    hard_jaccard_min: float = 0.25
    hard_overlap_min: int = 2
    soft_jaccard_min: float = 0.50
    locus_top_k: int = 2
"""
assert s.count(A) == 1
s = s.replace(A, B)

A2 = """    min_verbs: int = 2
    min_referents: int = 2  # |hard| >= this, OR |soft| >= min_soft_referents
    min_soft_referents: int = 4
"""
B2 = """    min_verbs: int = 2
    min_referents: int = 2  # |hard| >= this, OR |soft| >= min_soft_referents
    min_soft_referents: int = 2
"""
assert s.count(A2) == 1
s = s.replace(A2, B2)

A3 = """    min_verb_intersection: int = 2
    min_hard_intersection: int = 2
    min_soft_intersection: int = 3
"""
B3 = """    min_verb_intersection: int = 2
    min_hard_intersection: int = 2
    min_soft_intersection: int = 2
"""
assert s.count(A3) == 1
s = s.replace(A3, B3)

# ---- 2. correct the stale MEASURED-PERFORMANCE block in the module docstring ----------
A4 = """    chosen point (recall-max s.t. false_merge_rate <= 0.02):
        recall = 0.2364  (13/55)      false_merge_rate = 0.0162  (10/616)
    unconstrained recall ceiling:
        recall = 0.4727  at false_merge_rate = 0.1039            <- rejected by the criterion
    detector controls: impossible thresholds fire 0/55; permissive thresholds fire 52/55,
    so the harness is proven able to report both a miss and a hit.
"""
B4 = """    chosen point (sweep v2; recall-max s.t. NEG1 <= 0.02 AND NEG2 <= 0.002):
        recall  = 0.2545  (14/55)
        NEG1    = 0.0179  (11/616)     authored `not a duplicate:` pairs
        NEG2    = 0.00069 (12/17399)   intra-document declared-distinct pairs
    unconstrained recall ceiling:
        recall = 0.3091 at NEG1=23/616, NEG2=26/17399  <- rejected by the criterion
    detector controls: impossible thresholds fire 0/55; permissive thresholds fire 52/55,
    so the harness is proven able to report both a miss and a hit.

    NEG2 EXISTS BECAUSE NEG1 WAS NOT ENOUGH.  NEG1 scored an earlier point clean at 1.62%
    while the build that point produced merged 15 records on the single shared word "gate"
    and 10 on "index".  All 616 NEG1 pairs live in the option families, which carry rich
    mechanism prose; the failure lives in the classes with NO mechanism field.  A control
    measured on a population that excludes the failure mode is a weak control -- the same
    defect class as a probe silent in both states, one level up.  The signature-RICHNESS
    floors and the absolute-intersection floors are the fix; `controls.py` is the measurement.
"""
assert s.count(A4) == 1
s = s.replace(A4, B4)

A5 = """    Therefore the canonical count emitted by this module is an UPPER BOUND on the number of
distinct mechanisms in the corpus: it is UNDER-merged by a measured 76% of D3's addressable
range, never over-merged beyond the 1.62% audited false-merge budget."""
B5 = """    Therefore the canonical count emitted by this module is an UPPER BOUND on the number of
distinct mechanisms in the corpus: it is UNDER-merged by a measured ~75% of D3's addressable
range, never over-merged beyond the audited 1.79% / 0.069% false-merge budgets.
    D3 is also applied with COMPLETE linkage, not single linkage.  Single linkage produced 427
pairwise edges whose transitive closure collapsed 461 records -- a third of the corpus -- into
one cluster, while every individual edge was inside the audited pairwise budget.  A pairwise
false-merge rate does NOT bound cluster quality, because chaining a-b, b-c never has to
justify a-c."""
assert s.count(A5) == 1
s = s.replace(A5, B5)

p.write_text(s, encoding="utf-8")
print("patched dedup.py defaults + docstring")

# ---- 3. tie-break in sweep v2 --------------------------------------------------------
q = here / "_probe_dedup_sweep2.py"
t = q.read_text(encoding="utf-8")
A6 = """    adm.sort(key=lambda g: (-(g["recall"] or 0), (g["neg2_fmr"] or 0), (g["neg1_fmr"] or 0)))"""
B6 = """    def strictness(g):
        th = g["thresholds"]
        return (
            th["min_verbs"] + th["min_referents"] + th["min_soft_referents"]
            + th["min_verb_intersection"] + th["min_hard_intersection"]
            + th["min_soft_intersection"] + th["verb_jaccard_min"] + th["hard_jaccard_min"]
            + th["soft_jaccard_min"]
        )

    # Tie-break: among equally-performing points prefer the STRICTEST, because a looser point
    # that ties today admits more merges as the corpus grows.  Deterministic.
    adm.sort(
        key=lambda g: (
            -(g["recall"] or 0), (g["neg2_fmr"] or 0), (g["neg1_fmr"] or 0), -strictness(g)
        )
    )"""
assert t.count(A6) == 1
t = t.replace(A6, B6)
q.write_text(t, encoding="utf-8")
print("SUCCESS:patch-operating-point")
