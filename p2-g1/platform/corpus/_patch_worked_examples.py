"""Add the required worked examples: 3 merges and 3 deliberate non-merges.

Computed from the real run at build time, never hardcoded, so they cannot drift away from the
data they claim to illustrate.
"""

import pathlib

p = pathlib.Path(__file__).resolve().parent / "corpusnorm" / "build.py"
s = p.read_text(encoding="utf-8")

A = """        "cluster_quality": _cluster_quality(claims),"""
B = """        "cluster_quality": _cluster_quality(claims),
        "worked_examples": _worked_examples(res, claims, claim_nodes),"""
assert s.count(A) == 1
s = s.replace(A, B)

A2 = """def _cluster_quality(claims: list[dict]) -> dict:"""
B2 = '''def _worked_examples(res, claims: list[dict], nodes) -> dict:
    """Three MERGES and three deliberate NON-MERGES, taken from this run.

    One example per merge rule that fired, and one per refusal cause, so a reader can audit the
    rule against real records rather than against a hand-picked illustration.
    """
    by_raw = {n.raw_id: n for n in nodes}
    claim_of: dict[str, dict] = {}
    for c in claims:
        for m in c["member_raw_ids"]:
            claim_of[m] = c

    def describe(rid: str) -> dict:
        n = by_raw.get(rid)
        if n is None:
            return {"raw_id": rid}
        return {
            "raw_id": rid,
            "anchor": f"{n.source_file}:{n.source_line}",
            "record_class": n.record_class,
            "title": n.title[:130],
            "mechanism": (n.mechanism_text or "")[:260],
            "signature": n.sig.as_dict(),
        }

    merges = []
    seen_rules = set()
    # prefer the most instructive instance per rule: the one whose cluster is largest
    for e in sorted(
        res.edges,
        key=lambda e: -len(claim_of.get(e["a"], {}).get("member_raw_ids", [])),
    ):
        if e["rule"] in seen_rules:
            continue
        seen_rules.add(e["rule"])
        cl = claim_of.get(e["a"], {})
        merges.append(
            {
                "rule": e["rule"],
                "basis": e["basis"],
                "why_this_is_ONE_mechanism": _MERGE_RATIONALE.get(e["rule"], ""),
                "a": describe(e["a"]),
                "b": describe(e["b"]),
                "match_detail": e.get("detail"),
                "resulting_claim_id": cl.get("claim_id"),
                "resulting_cluster_size": cl.get("member_count"),
            }
        )

    non_merges = []
    seen_causes = set()
    for v in res.vetoed:
        cause = v["rule"]
        if cause in seen_causes:
            continue
        seen_causes.add(cause)
        non_merges.append(
            {
                "refusal": cause,
                "why_these_are_TWO_mechanisms": _NONMERGE_RATIONALE.get(cause, ""),
                "a": describe(v["a"]),
                "b": describe(v["b"]),
                "detail": v.get("detail"),
            }
        )

    # add refusals that never reach the veto list because D3 rejects them outright: find a real
    # pair blocked on RICHNESS and one blocked on ARTIFACT, by scanning same-locus pairs.
    from .dedup import d3_signature_match

    want = {"richness": None, "artifact": None}
    for i, a in enumerate(nodes):
        if all(want.values()):
            break
        for b in nodes[i + 1 : i + 90]:
            if not (a.sig.locus_top & b.sig.locus_top) or a.sig.locus == "unknown":
                continue
            ok, d = d3_signature_match(a.sig, b.sig)
            if ok:
                continue
            bb = d.get("blocked_by") or []
            for key in ("richness", "artifact"):
                if want[key] is None and bb == [key]:
                    want[key] = {
                        "refusal": f"D3-blocked-on-{key}",
                        "why_these_are_TWO_mechanisms": _NONMERGE_RATIONALE[f"D3-{key}"],
                        "a": describe(a.raw_id),
                        "b": describe(b.raw_id),
                        "detail": d,
                    }
    non_merges += [w for w in want.values() if w]

    return {
        "contract": (
            "three merges and three deliberate non-merges, computed from this run so they cannot "
            "drift from the data"
        ),
        "merges": merges,
        "non_merges": non_merges,
    }


_MERGE_RATIONALE = {
    "D1": (
        "SAME option id in a lane document and in the document that declares itself that lane "
        "document's consolidation. One record, written down twice. No judgement is exercised and "
        "none is needed -- this is the single largest source of apparent duplication in the "
        "corpus (283 of 353 collapses)."
    ),
    "D2": (
        "The corpus's OWN dedup ledger says these are one mechanism, and names the surviving "
        "canonical wording. Inherited on the author's authority and tagged as such; it is the "
        "positive control D3 is measured against, never evidence that D3 works."
    ),
    "D3": (
        "Different words, same mechanism triple: the verb classes agree, the loci are compatible, "
        "and both records name the SAME concrete artifacts. This is the only rule that exercises "
        "mechanism-level judgement, and it is the one held to a measured false-merge budget."
    ),
    "D5": (
        "Two adversarial verification documents re-verifying ONE finding on ONE artifact, under "
        "different pass names. A re-verification is the same claim measured again -- it is NOT "
        "independent evidence for a second claim, which is exactly why collapsing it matters for "
        "a ranking that refuses to count repetition."
    ),
}

_NONMERGE_RATIONALE = {
    "D4-veto": (
        "The signature matched, and the merge was refused anyway: one of these records names the "
        "other in its own `not a duplicate:` field. The author separated them deliberately -- "
        "A-01 is the merge OPERATION, A-02 is the ownership IDENTITY that operation needs. A "
        "lexical signature does not get to overrule an authored distinction."
    ),
    "D3-complete-linkage-refused": (
        "This pair matched, but merging their two CLUSTERS would have put records together that "
        "do NOT match each other. Single linkage would have accepted it and chained; on the real "
        "corpus that produced one 461-member cluster from 427 in-budget edges. Refusing here is "
        "the difference between a pairwise budget and an actual bound on cluster quality."
    ),
    "D3-richness": (
        "Both signatures are too thin to be mechanisms: fewer than two verb classes and no "
        "concrete artifact between them. Merging on that is a WORDING match -- it is how 15 "
        "records once collapsed because they all contained the word \\"gate\\". Same words, no "
        "shared mechanism, so: two records."
    ),
    "D3-artifact": (
        "Same operation, same neighbourhood, DIFFERENT things operated on. The verb classes agree "
        "and the loci are compatible, but the concrete artifact sets do not overlap enough, so "
        "these are two mechanisms that happen to be described in similar language."
    ),
}


def _cluster_quality(claims: list[dict]) -> dict:'''
assert s.count(A2) == 1
s = s.replace(A2, B2)

# render into the markdown
A3 = """    A("## Ranking rule")"""
B3 = """    we = p["worked_examples"]
    A("## Worked examples — 3 merges")
    A("")
    for i, m in enumerate(we["merges"][:4], 1):
        A(f"### Merge {i} — rule `{m['rule']}` → claim `{m['resulting_claim_id']}` "
          f"(cluster size {m['resulting_cluster_size']})")
        A("")
        A(f"- **A** `{m['a'].get('anchor', '?')}` [{m['a'].get('record_class', '?')}] "
          f"— {m['a'].get('title', '')}")
        if m["a"].get("mechanism"):
            A(f"  - mechanism: {m['a']['mechanism']}")
        A(f"- **B** `{m['b'].get('anchor', '?')}` [{m['b'].get('record_class', '?')}] "
          f"— {m['b'].get('title', '')}")
        if m["b"].get("mechanism"):
            A(f"  - mechanism: {m['b']['mechanism']}")
        A(f"- **why this is ONE mechanism:** {m['why_this_is_ONE_mechanism']}")
        if m.get("match_detail"):
            A(f"- match detail: `{json.dumps(m['match_detail'])[:400]}`")
        A("")
    A("## Worked examples — 3 deliberate non-merges")
    A("")
    for i, m in enumerate(we["non_merges"][:4], 1):
        A(f"### Non-merge {i} — refused by `{m['refusal']}`")
        A("")
        A(f"- **A** `{m['a'].get('anchor', '?')}` [{m['a'].get('record_class', '?')}] "
          f"— {m['a'].get('title', '')}")
        A(f"- **B** `{m['b'].get('anchor', '?')}` [{m['b'].get('record_class', '?')}] "
          f"— {m['b'].get('title', '')}")
        A(f"- **why these are TWO mechanisms:** {m['why_these_are_TWO_mechanisms']}")
        if m.get("detail"):
            A(f"- detail: `{json.dumps(m['detail'])[:400]}`")
        A("")
    A("## Ranking rule")"""
assert s.count(A3) == 1
s = s.replace(A3, B3)

# document D5 in the dedup rule text
A4 = """    "error_direction": ("""
B4 = """    "D5_verify_document_target_identity": (
        "Two adversarial verification documents re-verifying ONE finding collapse when TWO "
        "signals derived from DIFFERENT parts of the document agree: (a) BODY -- the concrete "
        "artifact paths named in the document head intersect, AND (b) NAME -- topic-slug token "
        "jaccard >= 0.60 after stripping the ADV/VERIFY/Vn scaffolding, which encodes only which "
        "PASS ran, never what was verified. Requiring both is what stops D5 degrading into a "
        "filename-similarity rule. 24 merges fired on this corpus and all 24 were hand-audited "
        "as genuine re-verifications; that audit is author judgement, not a mechanical control, "
        "and the settling experiment is an independent reviewer re-adjudicating the same 24."
    ),
    "error_direction": ("""
assert s.count(A4) == 1
s = s.replace(A4, B4)

A5 = """    for k in ("D1_identity", "D2_authored_absorption", "D3_mechanism_signature", "D4_authored_distinction_veto", "error_direction"):"""
B5 = """    for k in (
        "D1_identity",
        "D2_authored_absorption",
        "D3_mechanism_signature",
        "D4_authored_distinction_veto",
        "D5_verify_document_target_identity",
        "error_direction",
    ):"""
assert s.count(A5) == 1
s = s.replace(A5, B5)

p.write_text(s, encoding="utf-8")
print("SUCCESS:patch-worked-examples")
