"""Two fixes.

(1) SCOPE THE THIN-SIGNATURE GATE.  It fired on 51 clusters, and attribution showed all 51 were
    D1 (identity) or D1+D2 merges with ZERO D3 edges.  A D1 merge collapses the SAME option id
    appearing in a lane doc and in the doc that declares itself that lane doc's consolidation --
    correct regardless of how thin the mechanism prose is.  The gate must therefore fire only on
    clusters whose merges actually include a D3 (signature-derived) edge.  Left unscoped it was a
    gate that reports a defect where none exists, which is worse than no gate.

(2) ADD D5 -- VERIFY-DOCUMENT TARGET IDENTITY.  121 of the 1,291 raw records are adversarial
    verification documents, and the corpus re-verifies the same finding repeatedly under
    different filenames (`ADV-VERIFY-ledger-mojibake.md`, `ADV-VERIFY-ledger-mojibake-main.md`,
    `ADV-V9-VERIFY-ledger-mojibake.md`).  A re-verification of one finding is NOT independent
    evidence for a different claim -- collapsing them is the whole point of this unit, and
    leaving them apart would inflate the canonical count with the same claim counted N times.
    D3 misses them because a verify doc's mechanism text is one short target line, so its
    signature is below the richness floor.

    D5 requires TWO signals that are derived from different parts of the document, so it is not
    a filename-similarity rule wearing a disguise:
      (a) BODY signal   -- the sets of concrete artifact paths named in the document head
                           must intersect (this comes from the prose, not the name), AND
      (b) NAME signal   -- topic-slug token Jaccard >= 0.6 after stripping the ADV/VERIFY/Vn
                           scaffolding that encodes only WHICH PASS ran, not WHAT was verified.
    Side qualifiers (`main`, `patch`, `rerun`) are deliberately NOT stripped: a 0.6 Jaccard
    tolerates one extra token, so `{ledger,mojibake}` still matches `{ledger,mojibake,main}`
    (2/3), while a genuinely different topic drops below the floor on its own.
"""

import pathlib

here = pathlib.Path(__file__).resolve().parent

# ---------------------------------------------------------------- dedup.py: D5
p = here / "corpusnorm" / "dedup.py"
s = p.read_text(encoding="utf-8")

A = """def d4_veto(a: Node, b: Node) -> bool:"""
B = '''_RE_SCAFFOLD = re.compile(
    r"^(?:adv+|advv?x?|adv\\d+[a-z]?|v\\d+[a-z]?|verify|verified|adversarial|crossverify|"
    r"cross|rerun|runner|doc|md|lens|lane)$",
    re.I,
)
_RE_DOC_PATH = re.compile(
    r"\\b((?:[\\w.@-]+/)+[\\w.@-]+\\.(?:py|json|md|mjs|js|ps1|sh|ya?ml))\\b"
)


def verify_topic_slug(local_id: str) -> frozenset[str]:
    """Filename -> topic tokens, with the pass-number scaffolding removed.

    `ADV-V9-VERIFY-ledger-mojibake` -> {ledger, mojibake}.  The stripped tokens encode WHICH
    PASS ran, never WHAT was verified, so removing them is lossless for topic identity.
    """
    toks = [t for t in re.split(r"[-_.\\s]+", local_id or "") if t]
    keep = [t.lower() for t in toks if not _RE_SCAFFOLD.match(t) and not t.isdigit()]
    return frozenset(keep)


def verify_target_paths(body: str) -> frozenset[str]:
    """Concrete artifact paths named in the document head -- the BODY signal for D5."""
    return frozenset(m.group(1).lower().lstrip("./") for m in _RE_DOC_PATH.finditer(body or ""))


D5_SLUG_JACCARD_MIN = 0.60


def d5_verify_same_target(a: Node, b: Node) -> tuple[bool, dict]:
    """Two verification documents re-verifying ONE finding."""
    if a.record_class != "verify_doc" or b.record_class != "verify_doc":
        return False, {"skipped": "not-both-verify-docs"}
    pa, pb = verify_target_paths(a.body), verify_target_paths(b.body)
    sa, sb = verify_topic_slug(a.local_id), verify_topic_slug(b.local_id)
    body_ok = bool(pa & pb)
    sj = jaccard(sa, sb)
    name_ok = sj >= D5_SLUG_JACCARD_MIN
    detail = {
        "shared_target_paths": sorted(pa & pb)[:4],
        "slug_jaccard": round(sj, 3),
        "slug_a": sorted(sa),
        "slug_b": sorted(sb),
        "body_signal": body_ok,
        "name_signal": name_ok,
    }
    return (body_ok and name_ok), detail


def d4_veto(a: Node, b: Node) -> bool:'''
assert s.count(A) == 1
s = s.replace(A, B)

# run D5 after D2, before D3, so D3's complete-linkage sees the verify clusters
A2 = """    # ---- D3 mechanism signature (blocked by D4) --------------------------------------"""
B2 = """    # ---- D5 verify-document target identity ------------------------------------------
    vdocs = [n for n in nodes if n.record_class == "verify_doc"]
    for i in range(len(vdocs)):
        for j in range(i + 1, len(vdocs)):
            a, b = vdocs[i], vdocs[j]
            if dsu.find(a.raw_id) == dsu.find(b.raw_id):
                continue
            ok, detail = d5_verify_same_target(a, b)
            if not ok:
                continue
            if dsu.union(a.raw_id, b.raw_id):
                edges.append(
                    {
                        "a": a.raw_id,
                        "b": b.raw_id,
                        "rule": "D5",
                        "basis": "verify-doc-target-identity",
                        "detail": detail,
                    }
                )

    # ---- D3 mechanism signature (blocked by D4) --------------------------------------"""
assert s.count(A2) == 1
s = s.replace(A2, B2)
p.write_text(s, encoding="utf-8")
print("patched dedup.py: D5 added")

# ---------------------------------------------------------------- build.py: scope the gate
q = here / "corpusnorm" / "build.py"
t = q.read_text(encoding="utf-8")

A3 = """    thin = [
        c["claim_id"]
        for c in claims
        if c["member_count"] > 1
        and len(c["mechanism_signature"]["verbs"]) < 2
        and not c["mechanism_signature"]["hard_artifacts"]
    ]"""
B3 = """    # SCOPED to D3-bearing clusters.  Unscoped this fired on 51 clusters, every one of which
    # was a D1 identity merge (the same option id in a lane doc and in the doc that declares
    # itself that lane doc's consolidation) -- correct however thin the prose is.  A gate that
    # reports a defect where none exists is worse than no gate.
    thin = [
        c["claim_id"]
        for c in claims
        if c["member_count"] > 1
        and any(e["rule"] == "D3" for e in c["duplicate_of_edges"])
        and len(c["mechanism_signature"]["verbs"]) < 2
        and not c["mechanism_signature"]["hard_artifacts"]
    ]"""
assert t.count(A3) == 1
t = t.replace(A3, B3)

A4 = """        "note": (
            "thin_signature_count MUST be 0: a multi-member cluster whose signature has <2 verb "
            "classes and no concrete artifact was merged on wording, not mechanism"
        ),"""
B4 = """        "note": (
            "thin_signature_count MUST be 0: a D3-MERGED cluster whose signature has <2 verb "
            "classes and no concrete artifact was merged on wording, not mechanism. Scoped to "
            "D3 because D1/D2 merges are identity/authored and do not consult the signature."
        ),"""
assert t.count(A4) == 1
t = t.replace(A4, B4)
q.write_text(t, encoding="utf-8")
print("SUCCESS:patch-d5-and-gate")
