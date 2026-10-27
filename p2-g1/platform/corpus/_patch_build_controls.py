"""Wire the second negative control + cluster-quality diagnostics into the build payload."""

import pathlib

p = pathlib.Path(__file__).resolve().parent / "corpusnorm" / "build.py"
s = p.read_text(encoding="utf-8")

A = """from . import rank as R
from .dedup import ("""
B = """from . import rank as R
from .controls import intra_document_control
from .dedup import (
    d3_signature_match,"""
assert s.count(A) == 1
s = s.replace(A, B)

A2 = """    res = dedup(claim_nodes, ledger, DEFAULT_T)
    val = validate(claim_nodes, ledger, DEFAULT_T)
"""
B2 = """    res = dedup(claim_nodes, ledger, DEFAULT_T)
    val = validate(claim_nodes, ledger, DEFAULT_T)
    val["negative_control_2_intra_document"] = intra_document_control(
        claim_nodes, d3_signature_match, DEFAULT_T
    )
"""
assert s.count(A2) == 1
s = s.replace(A2, B2)

A3 = """        "claims": claims,
        "d4_vetoed_sample": res.vetoed[:20],
    }"""
B3 = """        "cluster_quality": _cluster_quality(claims),
        "claims": claims,
        "refused_merges_sample": res.vetoed[:24],
    }"""
assert s.count(A3) == 1
s = s.replace(A3, B3)

# split the misleading single veto counter into its two real causes
A4 = """            "merge_edges_by_rule": _rule_census(res.edges),
            "d4_vetoed_merges": len(res.vetoed),"""
B4 = """            "merge_edges_by_rule": _rule_census(res.edges),
            "refused_merges_by_reason": _rule_census(res.vetoed),"""
assert s.count(A4) == 1
s = s.replace(A4, B4)

A5 = """def _rule_census(edges) -> dict:"""
B5 = '''def _cluster_quality(claims: list[dict]) -> dict:
    """Cluster-level diagnostics.

    A pairwise false-merge rate does NOT bound cluster quality: single-linkage chaining once
    produced a 461-member cluster here while every individual edge was inside budget.  So the
    size distribution and the thin-signature census are published as first-class numbers.
    """
    sizes = sorted((c["member_count"] for c in claims), reverse=True)
    hist: dict[int, int] = {}
    for n in sizes:
        hist[n] = hist.get(n, 0) + 1
    thin = [
        c["claim_id"]
        for c in claims
        if c["member_count"] > 1
        and len(c["mechanism_signature"]["verbs"]) < 2
        and not c["mechanism_signature"]["hard_artifacts"]
    ]
    return {
        "max_cluster_size": sizes[0] if sizes else 0,
        "singletons": hist.get(1, 0),
        "size_histogram": dict(sorted(hist.items())),
        "multi_member_clusters": sum(v for k, v in hist.items() if k > 1),
        "thin_signature_multi_member_clusters": thin,
        "thin_signature_count": len(thin),
        "note": (
            "thin_signature_count MUST be 0: a multi-member cluster whose signature has <2 verb "
            "classes and no concrete artifact was merged on wording, not mechanism"
        ),
    }


def _rule_census(edges) -> dict:'''
assert s.count(A5) == 1
s = s.replace(A5, B5)

# md render: replace the veto row and add the cluster-quality + NEG2 rows
A6 = """    A(f"| merges blocked by the D4 authored-distinction veto | {c['d4_vetoed_merges']} |")"""
B6 = """    A(f"| refused merges by reason | {c['refused_merges_by_reason']} |")
    q = p["cluster_quality"]
    A(f"| max cluster size | {q['max_cluster_size']} |")
    A(f"| singleton claims | {q['singletons']} |")
    A(f"| multi-member clusters | {q['multi_member_clusters']} |")
    A(f"| thin-signature multi-member clusters (must be 0) | **{q['thin_signature_count']}** |")"""
assert s.count(A6) == 1
s = s.replace(A6, B6)

A7 = """    A(f"| NEGATIVE (authored `not a duplicate:` pairs, D4 off) — must NOT fire | {nc['pairs']} | {nc['d3_fired_falsely']} | false-merge **{nc['false_merge_rate']}** |")
    A("")"""
B7 = """    A(f"| NEGATIVE-1 (authored `not a duplicate:` pairs, D4 off) — must NOT fire | {nc['pairs']} | {nc['d3_fired_falsely']} | false-merge **{nc['false_merge_rate']}** |")
    n2 = v["negative_control_2_intra_document"]
    A(f"| NEGATIVE-2 (intra-document declared-distinct pairs) — must NOT fire | {n2['pairs']} | {n2['d3_fired_falsely']} | false-merge **{n2['false_merge_rate']}** |")
    A("")
    A("**NEGATIVE-2 exists because NEGATIVE-1 was not enough, and that is the sharpest lesson "
      "in this unit.** NEG-1 scored an earlier operating point clean at 1.62% while the build "
      "that point produced merged 15 records on the single shared word \\"gate\\" and 10 on "
      "\\"index\\". All 616 NEG-1 pairs live in the option families, which carry rich hand-written "
      "mechanism prose; the failure lives in the classes that carry NO mechanism field at all "
      "(blueprints, presets, protocols, archaeology, verify docs). A control measured on a "
      "population that structurally excludes the failure mode is a weak control — the same "
      "defect class as a probe that is silent in both states, one level up. The signature-"
      "richness and absolute-intersection floors are the fix; `controls.py` is the measurement.")
    A("")
    A("**A pairwise false-merge rate does not bound CLUSTER quality either.** Single-linkage D3 "
      "produced 427 edges whose transitive closure collapsed 461 records — a third of the "
      "corpus — into one claim, with every individual edge inside the audited budget, because "
      "chaining a-b, b-c never has to justify a-c. D3 therefore runs with COMPLETE linkage: a "
      "record joins a cluster only if it matches every member, and an over-budget linkage check "
      "is refused rather than approximated.")
    A("")"""
assert s.count(A7) == 1
s = s.replace(A7, B7)

p.write_text(s, encoding="utf-8")
print("SUCCESS:patch-build-controls")
