#!/usr/bin/env python
"""Phase 8 - RULE-BASED matching (`_USER-PROMPTS.md:10954`, "semantic and rule-based").

The rule lane is the high-PRECISION half of the router. It fires only on evidence a
human would accept without argument -- the user typed the capability's name, its
invoke token, one of its declared tags, or a phrase it declares as its own trigger.
Everything fuzzier is the semantic lane's job.

Two properties make this lane worth having separately rather than folding into scores:

1. **It is explainable by construction.** Each hit carries the rule that fired and the
   literal matched span, so `router.explain()` has real evidence to quote rather than a
   cosine number. The spec requires an "explanation of why a capability was selected";
   a similarity score is not an explanation.

2. **It can go NEGATIVE.** `anti_triggers` (mined from "Do NOT use for ..." prose) apply
   a DEMOTION. No prior router on this estate reads that field, yet the live corpus
   states it 152 times -- authors have already written down the confusable neighbours,
   and the information was being discarded. Demotion, not exclusion: an anti-trigger is
   authorial guidance, not a proof, so it must not be able to make a capability
   unreachable when nothing else fits.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .descriptions import tokens

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .index import Capability, Index

# --------------------------------------------------------------------------- weights
# Chosen so that ONE exact-name hit outranks any achievable accumulation of weak
# signals, and so no stack of weak signals can reach the strong-evidence band.
W_EXACT_NAME = 1.00
W_INVOKE_TOKEN = 0.95
W_ID_SUBSTRING = 0.70
W_TRIGGER_PHRASE = 0.60
W_TAG = 0.30
W_CATEGORY = 0.22
W_FAMILY = 0.18
W_CLASS_HINT = 0.15
W_ANTI_TRIGGER = -0.55

#: Prose that names a capability CLASS. Lets "a workflow for landing a risky deploy"
#: prefer a blueprint over a same-topic skill without hard-filtering the alternatives.
CLASS_HINTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(workflow|blueprint|pipeline|orchestrat\w*|multi-?phase)\b", re.I
        ),
        "workflow",
    ),
    (
        re.compile(
            r"\b(council|deliberat\w*|panel|debate|adjudicat\w*|tribunal)\b", re.I
        ),
        "protocol",
    ),
    (re.compile(r"\b(preset|ready-?made|pre-?configured)\b", re.I), "preset"),
    (re.compile(r"\b(mcp|tool server|backend server)\b", re.I), "mcp"),
    (re.compile(r"\b(skill|how do i|walk me through)\b", re.I), "skill"),
    (re.compile(r"\b(agent|subagent|reviewer persona)\b", re.I), "agent"),
    (re.compile(r"\b(slash ?command|/[a-z][a-z0-9-]{2,})\b", re.I), "command"),
    (re.compile(r"\b(candidate|registry|prior art|survey)\b", re.I), "candidate"),
    (re.compile(r"\b(plugin|marketplace)\b", re.I), "plugin"),
)


@dataclass(frozen=True)
class RuleHit:
    """One rule firing, with the literal evidence that fired it."""

    rule: str
    weight: float
    evidence: str

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "weight": round(self.weight, 3),
            "evidence": self.evidence[:160],
        }


#: A name appearing in this many corpus records is treated as "distinctive enough" -- its
#: IDF is the 1.0 reference point for `name_distinctiveness`.
REFERENCE_DF = 5

#: Floor on name credit. A common-word name is discounted, never disqualified: `command:plan`
#: must still be reachable by someone who types "plan".
MIN_NAME_CREDIT = 0.25


@dataclass(frozen=True)
class RuleContext:
    """Corpus statistics the rule lane needs. Built once per index, reused per query."""

    frag_df: dict[str, int]
    idf: dict[str, float]
    default_idf: float
    reference_idf: float

    @classmethod
    def build(cls, idx: Index) -> RuleContext:
        df: Counter[str] = Counter()
        for r in idx.records:
            df.update(set(tokens(r.routing_text)))
        n = max(len(idx.records), 1)

        def _idf(d: float) -> float:
            return math.log(1.0 + (n - d + 0.5) / (d + 0.5))

        # An unseen term is maximally surprising, so it gets the highest IDF the corpus
        # can express rather than 0 -- otherwise a novel domain word in the query would
        # silently contribute nothing to coverage.
        return cls(
            frag_df=fragment_df(idx),
            idf={t: _idf(d) for t, d in df.items()},
            default_idf=_idf(0.0),
            reference_idf=_idf(min(REFERENCE_DF, max(n - 1, 1))),
        )

    def weight(self, term: str) -> float:
        return self.idf.get(term, self.default_idf)

    def name_distinctiveness(self, name: str) -> float:
        """How much a NAME match should be believed, in [MIN_NAME_CREDIT, 1.0].

        MEASURED DEFECT. `exact-name` fired at full weight 1.00 whenever the query merely
        contained the capability's name -- but some capabilities are NAMED WITH COMMON
        ENGLISH WORDS: `plugin:data`, `command:docs`, `command:plan`, `command:eval`,
        `command:status`, `command:start`. So the query "spin up a rented GPU box for a few
        hours and copy my data onto it" fired exact-name for `plugin:data` at 1.00 and beat
        `mcp:cloud-hub`, whose description is literally about renting GPU boxes.

        The name lane was the last one still asserting literal evidence without asking
        whether the literal was distinctive -- the same error already fixed for fragments
        and for trigger overlap. Credit now scales with the name's corpus rarity, measured
        against the IDF of a term appearing in `REFERENCE_DF` records: a name at least that
        rare is fully believed, a commoner one is discounted toward MIN_NAME_CREDIT.

        Multi-segment names ("reframe-video-cutting") are exempt -- a hyphenated compound is
        an identifier by construction and cannot be typed accidentally.
        """
        parts = [p for p in re.split(r"[.:_\-/]", name.lower()) if p]
        if len(parts) > 1:
            return 1.0
        ref = self.reference_idf or 1.0
        return max(MIN_NAME_CREDIT, min(1.0, self.weight(name.lower()) / ref))


def _phrase_overlap(
    query_toks: set[str], phrase: str, ctx: RuleContext | None = None
) -> tuple[float, str]:
    """How much of the QUERY's discriminative content this trigger phrase explains.

    Normalized by the QUERY, IDF-weighted.

    MEASURED DEFECT this replaces: the first version normalized by the PHRASE
    (`|shared| / |phrase|`), which made the threshold un-satisfiable for long triggers.
    `skill:reframe` declares "Use when the user wants to convert, reframe, or crop a
    landscape video to vertical ... turn long horizontal footage into a portrait clip"
    (~15 content tokens). For the query "make my landscape video vertical for tiktok"
    the shared set was {landscape, video, vertical} -- i.e. essentially ALL of the
    query's intent -- yet scored 3/15 = 0.20 against a 0.60 threshold and never fired,
    so a *research* skill won a *reframing* query on a name fragment instead.

    Query-normalization asks the right question: "does this trigger account for what
    the user actually asked?" That is length-invariant in the phrase, which is the
    property a corpus with 6-to-400-character triggers requires.
    """
    pt = set(tokens(phrase))
    if len(pt) < 2 or not query_toks:
        return 0.0, ""
    hit = pt & query_toks
    if not hit:
        return 0.0, ""
    if ctx is None:
        return len(hit) / len(query_toks), " ".join(sorted(hit))
    total = sum(ctx.weight(t) for t in query_toks)
    if total <= 0:  # pragma: no cover - only for an all-zero-IDF query
        return 0.0, ""
    return sum(ctx.weight(t) for t in hit) / total, " ".join(sorted(hit))


#: A trigger phrase must be this covered by the query before it counts. Below it, the
#: overlap is ambient domain vocabulary rather than the author's stated trigger.
TRIGGER_MIN_COVERAGE = 0.60

#: An anti-trigger needs HIGHER coverage than a positive trigger before it demotes.
#: Asymmetry is deliberate: a wrong demotion hides a correct capability (a recall loss
#: the user cannot see), while a wrong promotion is visible and cheap to ignore.
ANTI_MIN_COVERAGE = 0.70


#: A name-fragment shared by more than this many capabilities is a DOMAIN WORD, not an
#: identifier, and must not fire the literal-evidence lane.
#:
#: MEASURED DEFECT this constant exists to close: without it, the query "make my
#: landscape video vertical for tiktok" was won by `skill:tiktok-public-research` on
#: `id-fragment='tiktok'` at weight 0.70, beating `skill:video-resize-aspect` whose
#: description is literally about turning a horizontal source into a vertical Reel. The
#: fragments "video" (33 capability names) and "panel" (7) were being treated as
#: name-level proof. `semantic.py` already applies inverse-document-frequency for
#: exactly this reason; the rule lane was asserting literal evidence without it. IDF is
#: not an optimization here, it is the difference between evidence and coincidence.
FRAGMENT_DF_MAX = 3


def fragment_df(idx: Index) -> dict[str, int]:
    """How many capabilities carry each fragment in their NAME or TAGS.

    Computed over the identifier/label space, not the prose: the question is "does this
    token distinguish one capability from its neighbours", which is a property of how
    names and tags are allocated. A prose-level DF would answer a different question and
    is already provided by `descriptions.corpus_stats`.
    """
    df: Counter[str] = Counter()
    for r in idx.records:
        parts = {f for f in re.split(r"[.:_\-/]", r.name.lower()) if len(f) >= 4}
        parts |= {str(t).lower() for t in (r.tags or ()) if len(str(t)) >= 4}
        df.update(parts)
    return dict(df)


def match_one(
    query: str, cap: Capability, ctx: RuleContext | None = None
) -> list[RuleHit]:
    """All rule hits for one capability. Empty list == the rule lane is silent.

    `ctx` supplies the corpus statistics that gate the fragment/tag lanes and weight
    trigger overlap. Passing None degrades to un-gated, un-weighted matching, which is
    correct ONLY for a single-record unit test; `match()` always supplies it.
    """
    q = query.lower()
    qt = set(tokens(query))
    hits: list[RuleHit] = []

    frag_df = ctx.frag_df if ctx else {}
    name = cap.name.lower()
    # Exact name: require a word boundary so "reframe" does not match inside
    # "reframed-arguments", and require length >= 4 so short ids ("p01") do not
    # collide with ordinary prose.
    credit = ctx.name_distinctiveness(name) if ctx else 1.0
    if len(name) >= 4 and re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", q):
        hits.append(RuleHit("exact-name", W_EXACT_NAME * credit, cap.name))
    elif len(name) >= 6 and name.replace("-", " ") in q:
        hits.append(
            RuleHit(
                "exact-name-spaced", W_EXACT_NAME * credit, cap.name.replace("-", " ")
            )
        )

    if cap.invoke and len(cap.invoke) >= 4 and cap.invoke.lower() in q:
        hits.append(RuleHit("invoke-token", W_INVOKE_TOKEN, cap.invoke))

    # Multi-word id fragments: `bp-rel-03`, `fused.…`, `wf-saved-…`. Two independent
    # gates, both learned from measured failures:
    #
    #   * DF gate -- the fragment must be rare across the name space (FRAGMENT_DF_MAX).
    #   * COVERAGE scaling -- the weight is scaled by how much of the capability's own
    #     name the fragment accounts for. Matching "tiktok" in `tiktok-public-research`
    #     is 1 of 3 segments and is NOT the same evidence as matching a whole name.
    #     Unscaled, that single fragment (0.70) beat `skill:reframe` on the query "make
    #     my landscape video vertical for tiktok" even though reframe was the TOP
    #     semantic match at 1.00 -- a research skill won a reframing task. This is the
    #     same normalization error as the trigger-overlap bug above, in the other
    #     direction: evidence must be scaled by how much of the thing it explains.
    segs = [f for f in re.split(r"[.:_\-/]", cap.name.lower()) if f]
    name_chars = sum(len(s) for s in segs) or 1
    for frag in [f for f in segs if len(f) >= 5]:
        if frag_df.get(frag, 1) > FRAGMENT_DF_MAX:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(frag)}(?![a-z0-9])", q):
            coverage = len(frag) / name_chars
            hits.append(RuleHit("id-fragment", W_ID_SUBSTRING * coverage, frag))
            break

    for phrase in cap.triggers:
        cov, ev = _phrase_overlap(qt, phrase, ctx)
        if cov >= TRIGGER_MIN_COVERAGE:
            hits.append(
                RuleHit("declared-trigger", W_TRIGGER_PHRASE * cov, ev or phrase[:80])
            )
            break

    for tag in cap.tags:
        t = str(tag).lower()
        # Same IDF gate as the fragment lane: a tag carried by dozens of capabilities
        # ("council", "moderate") is a bucket label, not evidence for one of them.
        if len(t) >= 4 and t in qt and frag_df.get(t, 1) <= FRAGMENT_DF_MAX * 3:
            hits.append(RuleHit("tag", W_TAG, t))
            break

    for cat in cap.categories:
        c = str(cat).lower().replace("-", " ")
        ct = set(tokens(c))
        if ct and len(ct & qt) / len(ct) >= 0.5:
            hits.append(RuleHit("category", W_CATEGORY, c))
            break

    if cap.family:
        ft = set(tokens(cap.family.replace("-", " ")))
        if ft and ft <= qt:
            hits.append(RuleHit("family", W_FAMILY, cap.family))

    for rx, cls in CLASS_HINTS:
        if cls == cap.cls and rx.search(query):
            hits.append(RuleHit("class-hint", W_CLASS_HINT, cls))
            break

    for phrase in cap.anti_triggers:
        cov, ev = _phrase_overlap(qt, phrase, ctx)
        if cov >= ANTI_MIN_COVERAGE:
            hits.append(
                RuleHit("anti-trigger", W_ANTI_TRIGGER * cov, ev or phrase[:80])
            )
            break

    return hits


def match(
    query: str, idx: Index, ctx: RuleContext | None = None
) -> dict[str, list[RuleHit]]:
    """Rule hits for every capability that produced at least one. id -> hits."""
    ctx = RuleContext.build(idx) if ctx is None else ctx
    out: dict[str, list[RuleHit]] = {}
    for cap in idx.records:
        hits = match_one(query, cap, ctx)
        if hits:
            out[cap.id] = hits
    return out


def score_of(hits: list[RuleHit]) -> float:
    """Collapse hits to one score.

    Positives use a diminishing-returns sum (strongest at full weight, each subsequent
    at half the previous) so a capability cannot climb by accumulating many weak rules.
    Negatives apply at FULL weight -- an anti-trigger is meant to bite.
    """
    pos = sorted((h.weight for h in hits if h.weight > 0), reverse=True)
    neg = sum(h.weight for h in hits if h.weight < 0)
    total = 0.0
    factor = 1.0
    for w in pos:
        total += w * factor
        factor *= 0.5
    return total + neg
