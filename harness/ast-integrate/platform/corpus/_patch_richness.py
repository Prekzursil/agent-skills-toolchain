"""One-shot patcher: add signature-richness + absolute-intersection floors to dedup.D3.

Written as a FILE rather than an inline heredoc because a literal apostrophe in a Bash-tool
command body breaks the tool's own quoting on this box (rules/common/windows-shell.md 10).
"""

import pathlib

p = pathlib.Path(__file__).resolve().parent / "corpusnorm" / "dedup.py"
s = p.read_text(encoding="utf-8")

A1 = """    verb_jaccard_min: float = 0.50
    verb_overlap_min: int = 3
    hard_jaccard_min: float = 0.25
    hard_overlap_min: int = 2
    soft_jaccard_min: float = 0.60
    locus_top_k: int = 2
"""
B1 = """    verb_jaccard_min: float = 0.50
    verb_overlap_min: int = 3
    hard_jaccard_min: float = 0.25
    hard_overlap_min: int = 2
    soft_jaccard_min: float = 0.60
    locus_top_k: int = 2

    # SIGNATURE RICHNESS.  Added after a measured false-merge class the FIRST negative control
    # could not see: 15 records collapsed because they all contained the single word "gate"
    # (verbs={GATE}, hard={}, soft={"gate"} -> every jaccard 1.0), and 10 more on the single
    # word "index" (a recall-index staleness verify doc merged with a per-index delay
    # blueprint).  A one-token signature is a WORDING match, not a mechanism match, which is
    # exactly what this unit is required not to do.  A record whose signature is thinner than
    # this may be merged by D1/D2 (identity / authored) but NEVER by D3.
    min_verbs: int = 2
    min_referents: int = 2  # |hard| >= this, OR |soft| >= min_soft_referents
    min_soft_referents: int = 4
    # ABSOLUTE intersection floors.  Jaccard alone is 1.0 for two identical singletons, which
    # is how a single shared word passed a 0.60 threshold.
    min_verb_intersection: int = 2
    min_hard_intersection: int = 2
    min_soft_intersection: int = 3
"""

A2 = """    vj = jaccard(a.verbs, b.verbs)
    hj = jaccard(a.hard, b.hard)
    sj = jaccard(a.soft, b.soft)
    v_overlap = len(a.verbs & b.verbs)
    h_overlap = len(a.hard & b.hard)

    locus_ok = bool(a.locus_top & b.locus_top)
    verb_ok = (vj >= t.verb_jaccard_min) or (v_overlap >= t.verb_overlap_min)

    if a.hard and b.hard:
        path = "hard"
        artifact_ok = (hj >= t.hard_jaccard_min) or (h_overlap >= t.hard_overlap_min)
    else:
        path = "concept" if (a.hard or b.hard) else "concept-both-empty"
        artifact_ok = sj >= t.soft_jaccard_min

    ok = verb_ok and locus_ok and artifact_ok
    return ok, {
        "verb_jaccard": round(vj, 3),
        "verb_overlap": v_overlap,
        "hard_jaccard": round(hj, 3),
        "hard_overlap": h_overlap,
        "soft_jaccard": round(sj, 3),
        "locus_compatible": locus_ok,
        "locus_a": a.locus,
        "locus_b": b.locus,
        "path": path,
        "blocked_by": [
            k
            for k, v in (("verb", verb_ok), ("locus", locus_ok), ("artifact", artifact_ok))
            if not v
        ],
    }
"""
B2 = '''    vj = jaccard(a.verbs, b.verbs)
    hj = jaccard(a.hard, b.hard)
    sj = jaccard(a.soft, b.soft)
    v_overlap = len(a.verbs & b.verbs)
    h_overlap = len(a.hard & b.hard)
    s_overlap = len(a.soft & b.soft)

    rich_ok = signature_is_rich(a, t) and signature_is_rich(b, t)
    locus_ok = bool(a.locus_top & b.locus_top)
    verb_ok = ((vj >= t.verb_jaccard_min) or (v_overlap >= t.verb_overlap_min)) and (
        v_overlap >= t.min_verb_intersection
    )

    if a.hard and b.hard:
        path = "hard"
        artifact_ok = ((hj >= t.hard_jaccard_min) or (h_overlap >= t.hard_overlap_min)) and (
            h_overlap >= t.min_hard_intersection
        )
    else:
        path = "concept" if (a.hard or b.hard) else "concept-both-empty"
        artifact_ok = sj >= t.soft_jaccard_min and s_overlap >= t.min_soft_intersection

    ok = rich_ok and verb_ok and locus_ok and artifact_ok
    return ok, {
        "verb_jaccard": round(vj, 3),
        "verb_overlap": v_overlap,
        "hard_jaccard": round(hj, 3),
        "hard_overlap": h_overlap,
        "soft_jaccard": round(sj, 3),
        "soft_overlap": s_overlap,
        "locus_compatible": locus_ok,
        "locus_a": a.locus,
        "locus_b": b.locus,
        "path": path,
        "signatures_rich": rich_ok,
        "blocked_by": [
            k
            for k, v in (
                ("richness", rich_ok),
                ("verb", verb_ok),
                ("locus", locus_ok),
                ("artifact", artifact_ok),
            )
            if not v
        ],
    }


def signature_is_rich(s: Signature, t: Thresholds = DEFAULT_T) -> bool:
    """A signature thin enough to match on one shared token is not a mechanism."""
    return len(s.verbs) >= t.min_verbs and (
        len(s.hard) >= t.min_referents or len(s.soft) >= t.min_soft_referents
    )
'''

for a, b in ((A1, B1), (A2, B2)):
    n = s.count(a)
    assert n == 1, f"anchor count {n} for {a[:50]!r}"
    s = s.replace(a, b)

p.write_text(s, encoding="utf-8")
print("SUCCESS:patch-richness two anchors replaced")
