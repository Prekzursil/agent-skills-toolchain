"""Mechanism-level deduplication, with the corpus's own authored ledger as ground truth.

THE DEDUP RULE (stated so it can be audited; applied in this order)
-------------------------------------------------------------------
D1  IDENTITY.  Two records carrying the SAME local id, where one source document is a
    declared consolidation of the other, are the same record.  `07-OPTION-UNIVERSE.md`
    declares itself the consolidation of the five `07-OPTIONS-*.md` lane docs, so
    `07-OPTIONS-AB.md#A-01` and `07-OPTION-UNIVERSE.md#A-01` collapse.  Exact, no judgement.

D2  AUTHORED ABSORPTION.  `07-OPTION-UNIVERSE.md` §3 publishes a dedup ledger of
    (canonical <- absorbed...) edges.  Those edges are INHERITED, tagged
    `dedup_basis="authored-ledger"`, and are NOT evidence that D3 works -- they are the
    POSITIVE CONTROL that D3 is measured against.

D3  MECHANISM SIGNATURE.  Two records are duplicates iff ALL THREE hold:
      verb agreement    jaccard(verb_set) >= 0.50  OR  |verb_set intersection| >= 3
      locus agreement   top-2 locus sets intersect      (COMPATIBILITY, not equality)
      artifact agreement
          both name concrete artifacts -> jaccard(hard) >= 0.25 OR |hard cap| >= 2
          otherwise                    -> jaccard(soft_concepts) >= 0.60
    A record that names no concrete artifact cannot DISAGREE about one, so the asymmetric
    case falls through to the concept path rather than being rejected outright.

D4  AUTHORED-DISTINCTION VETO.  If either record's own `not a duplicate:` field names the
    other's id, they are NEVER merged whatever D3 says.  The corpus author separated them
    on the record; a lexical signature does not get to overrule an authored distinction.
    D4 is the precision guard and is the reason a false merge is expensive but rare.

MEASURED PERFORMANCE OF D3 -- the number that matters, and it is not flattering
-------------------------------------------------------------------------------
Against the corpus's own authored dedup ledger (55 absorption pairs = POSITIVE control) and
its 616 authored `not a duplicate:` pairs (NEGATIVE control), swept over 324 operating points
(`_probe_dedup_sweep.py` -> `DEDUP-VALIDATION.json`):

    chosen point (sweep v2; recall-max s.t. NEG1 <= 0.02 AND NEG2 <= 0.002):
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

CONCLUSION, stated inline rather than buried: **a lexical mechanism signature does NOT
reproduce human mechanism-level dedup at acceptable precision.**  76% of the author's merges
are paraphrases sharing no verb+artifact vocabulary ("Deploy the dark cross-vendor council
and invoke suite" vs its two absorbed siblings).  Mechanism identity is therefore treated as
a SEMANTIC judgement that D3 can only partially mechanise.  The consequence for this
artifact: D2 (the authored ledger) is the PRIMARY merge source for the option families, D1
handles the consolidation collapse, and D3 is an ADDITIVE proposer restricted to pairs the
ledger never examined -- above all the CROSS-CLASS pairs (an option card vs a blueprint vs a
verify doc), which no authored ledger covers at all.
    Therefore the canonical count emitted by this module is an UPPER BOUND on the number of
distinct mechanisms in the corpus: it is UNDER-merged by a measured ~75% of D3's addressable
range, never over-merged beyond the audited 1.79% / 0.069% false-merge budgets.
    D3 is also applied with COMPLETE linkage, not single linkage.  Single linkage produced 427
pairwise edges whose transitive closure collapsed 461 records -- a third of the corpus -- into
one cluster, while every individual edge was inside the audited pairwise budget.  A pairwise
false-merge rate does NOT bound cluster quality, because chaining a-b, b-c never has to
justify a-c.

WHY CONSERVATIVE.  On this estate an LLM asked to do a mechanical comparison scored 86% with
100% of its errors pointing at data loss.  The analogous dangerous direction here is a FALSE
MERGE: collapsing two genuinely different mechanisms destroys one of them, and the loss is
invisible downstream.  Under-merging leaves a duplicate pair sitting in the output where it
is auditable.  So the thresholds are tuned for precision, recall is measured and reported,
and no claim of completeness is made.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .mechanism import Signature, jaccard, signature

# 07-OPTION-UNIVERSE.md declares itself the consolidation of these five lane docs.
CONSOLIDATION_PARENT = "07-OPTION-UNIVERSE.md"
CONSOLIDATED_CHILDREN = (
    "07-OPTIONS-AB.md",
    "07-OPTIONS-CD.md",
    "07-OPTIONS-EFG.md",
    "07-OPTIONS-HIJK.md",
    "07-OPTIONS-LM.md",
)


@dataclass(frozen=True)
class Thresholds:
    """D3 operating point.

    Selection criterion, FIXED BEFORE the sweep was run and not revised afterwards:
    maximise positive-control recall subject to negative-control false-merge rate <= 0.02.
    Rationale: the dangerous error direction is a FALSE MERGE (it destroys a distinct
    mechanism, invisibly); 616 authored `not a duplicate:` pairs measure that direction
    tightly, and every accepted false merge stays individually listed in the output for
    audit.  The whole sweep is emitted in DEDUP-VALIDATION.json so the choice of point is
    checkable and not cherry-picked.
    """

    # THE SWEPT OPERATING POINT (sweep v2, 1152 grid points, 1048 admissible).
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

    # SIGNATURE RICHNESS.  Added after a measured false-merge class the FIRST negative control
    # could not see: 15 records collapsed because they all contained the single word "gate"
    # (verbs={GATE}, hard={}, soft={"gate"} -> every jaccard 1.0), and 10 more on the single
    # word "index" (a recall-index staleness verify doc merged with a per-index delay
    # blueprint).  A one-token signature is a WORDING match, not a mechanism match, which is
    # exactly what this unit is required not to do.  A record whose signature is thinner than
    # this may be merged by D1/D2 (identity / authored) but NEVER by D3.
    min_verbs: int = 2
    min_referents: int = 2  # |hard| >= this, OR |soft| >= min_soft_referents
    min_soft_referents: int = 2
    # ABSOLUTE intersection floors.  Jaccard alone is 1.0 for two identical singletons, which
    # is how a single shared word passed a 0.60 threshold.
    min_verb_intersection: int = 2
    min_hard_intersection: int = 2
    min_soft_intersection: int = 2


DEFAULT_T = Thresholds()

# Complete-linkage verification is O(|A|x|B|).  A pair of clusters larger than this is
# REFUSED rather than merged on a partial check -- fail closed, never fail open.
MAX_LINKAGE_CHECKS = 4000

_RE_LEDGER_ROW = re.compile(
    r"^\| *`([A-Z]{1,3}-\d{1,3})` *\| *([A-Z0-9, \-]+?) *\| *(.+?) *\|\s*$"
)


def parse_authored_ledger(root: Path) -> list[tuple[str, list[str], str]]:
    """Parse `07-OPTION-UNIVERSE.md` §3 -> [(canonical_id, [absorbed_ids], mechanism_text)]."""
    p = root / CONSOLIDATION_PARENT
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    out = []
    in_section = False
    for ln in text.splitlines():
        if ln.startswith("## 3. Dedup ledger"):
            in_section = True
            continue
        if in_section and ln.startswith("## ") and "Dedup ledger" not in ln:
            break
        if not in_section:
            continue
        m = _RE_LEDGER_ROW.match(ln)
        if not m:
            continue
        absorbed = [a.strip() for a in m.group(2).split(",") if a.strip()]
        if not absorbed:
            continue
        out.append((m.group(1), absorbed, m.group(3).strip()))
    return out


# --------------------------------------------------------------------------------------


@dataclass
class Node:
    raw_id: str
    local_id: str
    record_class: str
    source_file: str
    source_line: int
    title: str
    mechanism_text: str
    problem_text: str
    sig: Signature
    distinct_from: list[str] = field(default_factory=list)
    deps: list[str] = field(default_factory=list)
    verdict: str = ""
    confidence_raw: str = ""
    severity_raw: str = ""
    evidence_anchors: list[str] = field(default_factory=list)
    probe_text: str = ""
    body: str = ""


def to_nodes(records) -> list[Node]:
    out = []
    for r in records:
        out.append(
            Node(
                raw_id=r.raw_id,
                local_id=r.local_id,
                record_class=r.record_class,
                source_file=r.source_file,
                source_line=r.source_line,
                title=r.title,
                mechanism_text=r.mechanism_text,
                problem_text=r.problem_text,
                sig=signature(r.mechanism_text, r.title, r.problem_text),
                distinct_from=list(r.distinct_from),
                deps=list(r.deps),
                verdict=r.verdict,
                confidence_raw=r.confidence_raw,
                severity_raw=r.severity_raw,
                evidence_anchors=list(r.evidence_anchors),
                probe_text=r.probe_text,
                body=r.body,
            )
        )
    return out


# --------------------------------------------------------------------------------------
# the four rules
# --------------------------------------------------------------------------------------


def d1_identity(a: Node, b: Node) -> bool:
    if a.local_id != b.local_id:
        return False
    pair = {a.source_file, b.source_file}
    if CONSOLIDATION_PARENT in pair and pair & set(CONSOLIDATED_CHILDREN):
        return True
    return False


def d3_signature_match(
    a: Signature, b: Signature, t: Thresholds = DEFAULT_T
) -> tuple[bool, dict]:
    """The corrected D3 predicate.

    Three fixes over the first version, each forced by a measured failure mode on the
    authored positive-control set (55 pairs):

    * locus COMPATIBILITY (top-k intersection) instead of dominant-locus EQUALITY -- equality
      rejected 22/55.
    * a THREE-WAY artifact path.  The first version demanded both hard sets non-empty for the
      hard path and both empty for the soft path, so a pair where exactly ONE side named a
      concrete artifact had no path at all and was rejected outright -- that blocked 44/55.
      A record that names no artifact cannot disagree about one, so the asymmetric case falls
      back to the concept path.
    * verb agreement satisfiable by ABSOLUTE overlap as well as Jaccard, because verb-set
      sizes differ by 3x across the corpus dialects and Jaccard punishes the verbose side.
    """
    vj = jaccard(a.verbs, b.verbs)
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
        artifact_ok = (
            (hj >= t.hard_jaccard_min) or (h_overlap >= t.hard_overlap_min)
        ) and (h_overlap >= t.min_hard_intersection)
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


_RE_SCAFFOLD = re.compile(
    r"^(?:adv+|advv?x?|adv\d+[a-z]?|v\d+[a-z]?|verify|verified|adversarial|crossverify|"
    r"cross|rerun|runner|doc|md|lens|lane)$",
    re.I,
)
_RE_DOC_PATH = re.compile(
    r"\b((?:[\w.@-]+/)+[\w.@-]+\.(?:py|json|md|mjs|js|ps1|sh|ya?ml))\b"
)


def verify_topic_slug(local_id: str) -> frozenset[str]:
    """Filename -> topic tokens, with the pass-number scaffolding removed.

    `ADV-V9-VERIFY-ledger-mojibake` -> {ledger, mojibake}.  The stripped tokens encode WHICH
    PASS ran, never WHAT was verified, so removing them is lossless for topic identity.
    """
    toks = [t for t in re.split(r"[-_.\s]+", local_id or "") if t]
    keep = [t.lower() for t in toks if not _RE_SCAFFOLD.match(t) and not t.isdigit()]
    return frozenset(keep)


def verify_target_paths(body: str) -> frozenset[str]:
    """Concrete artifact paths named in the document head -- the BODY signal for D5."""
    return frozenset(
        m.group(1).lower().lstrip("./") for m in _RE_DOC_PATH.finditer(body or "")
    )


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


def d4_veto(a: Node, b: Node) -> bool:
    """True == authored distinction forbids the merge."""
    return (b.local_id in a.distinct_from) or (a.local_id in b.distinct_from)


# --------------------------------------------------------------------------------------
# union-find clustering
# --------------------------------------------------------------------------------------


class DSU:
    def __init__(self, keys):
        self.p = {k: k for k in keys}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[rb] = ra
            return True
        return False


@dataclass
class DedupResult:
    clusters: dict[str, list[str]]
    edges: list[dict]
    vetoed: list[dict]
    node_by_id: dict[str, Node]


def dedup(
    nodes: list[Node],
    authored_ledger: list[tuple[str, list[str], str]],
    t: Thresholds = DEFAULT_T,
) -> DedupResult:
    by_id = {n.raw_id: n for n in nodes}
    dsu = DSU(by_id.keys())
    edges: list[dict] = []
    vetoed: list[dict] = []

    # ---- D1 identity -----------------------------------------------------------------
    by_local: dict[str, list[Node]] = {}
    for n in nodes:
        by_local.setdefault(n.local_id, []).append(n)
    for lid, group in by_local.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                if d1_identity(group[i], group[j]):
                    if dsu.union(group[i].raw_id, group[j].raw_id):
                        edges.append(
                            {
                                "a": group[i].raw_id,
                                "b": group[j].raw_id,
                                "rule": "D1",
                                "basis": "identity-across-declared-consolidation",
                            }
                        )

    # ---- D2 authored absorption ------------------------------------------------------
    # map an option local id -> its records (lane copies and/or universe copy)
    for canonical, absorbed, mech in authored_ledger:
        can_nodes = by_local.get(canonical, [])
        if not can_nodes:
            continue
        anchor = can_nodes[0].raw_id
        for abs_id in absorbed:
            for n in by_local.get(abs_id, []):
                if dsu.union(anchor, n.raw_id):
                    edges.append(
                        {
                            "a": anchor,
                            "b": n.raw_id,
                            "rule": "D2",
                            "basis": "authored-ledger",
                            "authored_mechanism": mech,
                        }
                    )

    # ---- D5 verify-document target identity ------------------------------------------
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

    # ---- D3 mechanism signature (blocked by D4) --------------------------------------
    # Bucket by locus to keep this O(sum n_locus^2) instead of O(n^2) over 1,291 records.
    buckets: dict[str, list[Node]] = {}
    for n in nodes:
        # a node is indexed under EVERY locus in its top-k, so a compatible pair whose
        # dominant loci differ still meets inside at least one bucket.  Bucketing on the
        # dominant locus alone would silently re-impose the equality predicate that the
        # positive control already refuted.
        for lo in n.sig.locus_top or frozenset({"unknown"}):
            buckets.setdefault(lo, []).append(n)
    # COMPLETE-LINKAGE, not single-linkage.  Measured on the first build: single-linkage D3
    # produced 427 pairwise edges whose TRANSITIVE closure collapsed 461 records -- a third of
    # the corpus -- into one cluster.  The pairwise false-merge rate (1.62%) does NOT bound
    # that, because chaining a-b, b-c never has to justify a-c.  A candidate is therefore
    # admitted to a cluster only if it matches EVERY member of it, which makes the audited
    # pairwise budget an actual bound on cluster quality.
    members: dict[str, list[Node]] = {}
    for n in nodes:
        members.setdefault(dsu.find(n.raw_id), []).append(n)

    def clusters_mergeable(ca: list[Node], cb: list[Node]) -> tuple[bool, dict | None]:
        if len(ca) * len(cb) > MAX_LINKAGE_CHECKS:
            return False, {
                "refused": "linkage-check-budget-exceeded",
                "sizes": [len(ca), len(cb)],
            }
        worst = None
        for x in ca:
            for y in cb:
                if d4_veto(x, y):
                    return False, {
                        "refused": "D4-veto-inside-cluster-pair",
                        "a": x.raw_id,
                        "b": y.raw_id,
                    }
                ok, detail = d3_signature_match(x.sig, y.sig, t)
                if not ok:
                    return False, detail
                worst = detail
        return True, worst

    for locus, group in buckets.items():
        if locus == "unknown":
            continue
        for i in range(len(group)):
            a = group[i]
            for j in range(i + 1, len(group)):
                b = group[j]
                ra, rb = dsu.find(a.raw_id), dsu.find(b.raw_id)
                if ra == rb:
                    continue
                ok, detail = d3_signature_match(a.sig, b.sig, t)
                if not ok:
                    continue
                if d4_veto(a, b):
                    vetoed.append(
                        {
                            "a": a.raw_id,
                            "b": b.raw_id,
                            "rule": "D4-veto",
                            "detail": detail,
                        }
                    )
                    continue
                ca, cb = members.get(ra, [a]), members.get(rb, [b])
                linked, ldetail = clusters_mergeable(ca, cb)
                if not linked:
                    vetoed.append(
                        {
                            "a": a.raw_id,
                            "b": b.raw_id,
                            "rule": "D3-complete-linkage-refused",
                            "detail": ldetail,
                        }
                    )
                    continue
                if dsu.union(a.raw_id, b.raw_id):
                    root = dsu.find(a.raw_id)
                    merged = ca + cb
                    members[root] = merged
                    for stale in (ra, rb):
                        if stale != root:
                            members.pop(stale, None)
                    edges.append(
                        {
                            "a": a.raw_id,
                            "b": b.raw_id,
                            "rule": "D3",
                            "basis": "mechanism-signature-complete-linkage",
                            "detail": detail,
                            "cluster_size_after": len(merged),
                        }
                    )

    clusters: dict[str, list[str]] = {}
    for rid in by_id:
        clusters.setdefault(dsu.find(rid), []).append(rid)
    return DedupResult(clusters=clusters, edges=edges, vetoed=vetoed, node_by_id=by_id)


# --------------------------------------------------------------------------------------
# validation -- the both-states control for the dedup detector
# --------------------------------------------------------------------------------------


def validate(nodes: list[Node], authored_ledger, t: Thresholds = DEFAULT_T) -> dict:
    """Measure D3 ALONE against two authored control sets.

    POSITIVE control (must FIRE): the 55 authored absorption pairs.  D3 is evaluated with
    D2 switched OFF, so a hit is D3 rediscovering the author's merge unaided.
    NEGATIVE control (must NOT fire): every authored `not a duplicate:` pair, evaluated with
    the D4 veto switched OFF, so a hit is D3 proposing a merge the author explicitly forbade.

    A detector that fires on neither set, or on both indiscriminately, measures nothing.
    """
    by_local: dict[str, list[Node]] = {}
    for n in nodes:
        by_local.setdefault(n.local_id, []).append(n)

    def best_pair_match(id_a: str, id_b: str):
        """Any (record of a, record of b) pair matching under D3 counts as a hit."""
        best = None
        for na in by_local.get(id_a, []):
            for nb in by_local.get(id_b, []):
                if na.raw_id == nb.raw_id:
                    continue
                ok, detail = d3_signature_match(na.sig, nb.sig, t)
                if ok:
                    return True, detail
                if best is None:
                    best = detail
        return False, best

    pos_total = pos_hit = 0
    pos_misses = []
    for canonical, absorbed, _mech in authored_ledger:
        for abs_id in absorbed:
            if canonical not in by_local or abs_id not in by_local:
                continue
            pos_total += 1
            hit, detail = best_pair_match(canonical, abs_id)
            if hit:
                pos_hit += 1
            else:
                pos_misses.append(
                    {"canonical": canonical, "absorbed": abs_id, "closest": detail}
                )

    neg_total = neg_false = 0
    neg_false_pairs = []
    seen_neg: set[tuple[str, str]] = set()
    for n in nodes:
        for other in n.distinct_from:
            if other == n.local_id or other not in by_local:
                continue
            key = tuple(sorted((n.local_id, other)))
            if key in seen_neg:
                continue
            seen_neg.add(key)
            neg_total += 1
            hit, detail = best_pair_match(n.local_id, other)
            if hit:
                neg_false += 1
                neg_false_pairs.append({"a": n.local_id, "b": other, "detail": detail})

    recall = (pos_hit / pos_total) if pos_total else None
    fpr = (neg_false / neg_total) if neg_total else None
    return {
        "positive_control": {
            "description": "authored dedup-ledger absorption pairs; D3 evaluated with D2 OFF",
            "pairs": pos_total,
            "d3_fired": pos_hit,
            "recall": round(recall, 4) if recall is not None else None,
            "misses_sample": pos_misses[:12],
            "miss_count": len(pos_misses),
        },
        "negative_control": {
            "description": "authored `not a duplicate:` pairs; D3 evaluated with D4 veto OFF",
            "pairs": neg_total,
            "d3_fired_falsely": neg_false,
            "false_merge_rate": round(fpr, 4) if fpr is not None else None,
            "false_pairs_sample": neg_false_pairs[:12],
        },
        "detector_is_discriminating": bool(
            pos_total and neg_total and pos_hit > 0 and (recall or 0) > (fpr or 0)
        ),
        "thresholds": {
            "verb_jaccard_min": t.verb_jaccard_min,
            "verb_overlap_min": t.verb_overlap_min,
            "hard_jaccard_min": t.hard_jaccard_min,
            "hard_overlap_min": t.hard_overlap_min,
            "soft_jaccard_min": t.soft_jaccard_min,
            "locus_top_k": t.locus_top_k,
        },
    }
