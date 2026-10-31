#!/usr/bin/env python
"""Phase 8 LABELLED QUERY SET - and a full disclosure of how it was labelled.

The task requires "precision and recall on a labelled query set you construct, and
disclose how you labelled it". The disclosure is the load-bearing part: a routing
evaluation is trivially gameable, and the two ways to game it are exactly the two ways
this file is structured to prevent.

GAME 1 - CIRCULARITY. Take a capability's description, use it as the query, and route
against that same description. Recall goes to ~1.0 and measures nothing but string
equality. Mitigation: tier L1 queries ARE derived from capability text, but the derived
sentence is REMOVED from that record's `routing_text` before the query runs
(`holdout_index`). The router must then match on the REST of the record. This converts
a circular test into a genuine held-out generalization test, and it is mechanical, so
no author judgement enters the label.

GAME 2 - AUTHOR LEAKAGE. Hand-write a query, hand-pick its gold label, and
unconsciously seed it with the winning keywords. Mitigation: tiers L2/L3/L4 are
author-labelled -- so every one of them reports `lexical_overlap`, the Jaccard overlap
between the query's content tokens and the gold record's OWN declared description.
A high-overlap "paraphrase" is a keyword giveaway and the number says so. `metrics.py`
reports the overlap distribution alongside precision/recall so a reader can discount
accordingly rather than take the score on trust.

TIERS
-----
  L1  held-out-trigger    mechanically generated; gold = the source capability;
                          the trigger sentence is withheld from the index
  L2  author-paraphrase   hand-written in different words; gold = author judgement;
                          lexical overlap REPORTED
  L3  negative            no capability legitimately fits; gold = EMPTY SET.
                          Tests the fallback and the router's ability to stay silent.
  L4  multi-label         several capabilities legitimately relevant; gold = all of
                          them. Tests recall@k WITHOUT rewarding a flood.

WHAT THIS SET IS NOT
--------------------
It is not a benchmark anyone else should cite as an absolute number. It is 60 queries
over one estate's inventory, authored by the same agent that wrote the router. Its
legitimate uses are (a) REGRESSION - the same set re-run after a change, and (b)
ABLATION - the same set with a component disabled. Both are comparisons against
itself, where author bias is held constant and therefore cancels. Treating the absolute
precision figure as a general claim about routing quality would be an overclaim; the
settling experiment for that would be an independently authored query set, which this
unit does not have (UNVERIFIED, stated inline).
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .descriptions import tokens

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .index import Index


@dataclass(frozen=True)
class Query:
    """One labelled query. `gold` is a frozenset of capability ids; empty = no-fit."""

    qid: str
    text: str
    gold: frozenset[str]
    tier: str
    note: str = ""
    #: For L1: the id whose routing_text must have `holdout_text` removed.
    holdout_id: str = ""
    holdout_text: str = ""

    def as_dict(self) -> dict:
        return {
            "qid": self.qid,
            "text": self.text,
            "gold": sorted(self.gold),
            "tier": self.tier,
            "note": self.note,
            "holdout_id": self.holdout_id,
        }


# ---------------------------------------------------------------------- L1 generation

#: Trigger phrases shorter than this carry too little content to be a fair query.
L1_MIN_CHARS = 40
#: ...and longer than this are a paragraph, not a request.
L1_MAX_CHARS = 220


def _clean_trigger(frag: str) -> str:
    """Turn a mined trigger fragment into something a person would plausibly type."""
    s = re.sub(r"\s+", " ", frag).strip(" .,;:-")
    s = re.sub(r"^(?:the\s+)?user\s+(?:wants?|asks?|needs?)\s+to\s+", "", s, flags=re.I)
    s = re.sub(r"^(?:you\s+)?(?:are|is)\s+", "", s, flags=re.I)
    return s.strip()


def _candidate_holdouts(r) -> list[tuple[str, str, str]]:
    """(sub_tier, raw_holdout, query_text) options for one record, best first.

    L1a uses a DECLARED TRIGGER ("Use when ..."). L1b falls back to the record's own
    declared description sentence.

    L1b is not padding -- it is the only way to cover most of the inventory. MEASURED
    over the live index: trigger prose exists for 251/328 skills and 4/18 agents and for
    **ZERO** of the 584 workflow / protocol / preset / candidate / mcp / command / plugin
    records. A trigger-only L1 therefore produced 4 queries, all skills, and could not
    measure blueprint or council routing at all.

    DISCLOSURE: an L1b query is phrased like documentation, not like a person, so L1b
    measures RETRIEVAL (leave-one-out: find the record from a fragment of its own text
    with that fragment removed) rather than paraphrase understanding. The two sub-tiers
    are reported separately for exactly that reason -- averaging them would let easy
    retrieval hide weak paraphrase handling.
    """
    opts: list[tuple[str, str, str]] = []
    for raw in r.triggers:
        text = _clean_trigger(raw)
        if (
            L1_MIN_CHARS <= len(text) <= L1_MAX_CHARS
            and r.name.lower() not in text.lower()
        ):
            opts.append(("L1a", raw, text))
    src = (r.desc_source or "").strip()
    if src:
        for sent in re.split(r"(?<=[.;])\s+", src):
            text = _clean_trigger(sent)
            if (
                L1_MIN_CHARS <= len(text) <= L1_MAX_CHARS
                and r.name.lower() not in text.lower()
            ):
                opts.append(("L1b", sent, text))
                break
    return opts


#: After the holdout, the source record must retain at least this many distinct content
#: tokens, or the query is UNANSWERABLE BY CONSTRUCTION and is not generated.
#:
#: MEASURED ARTIFACT this closes. L1b holds out a description sentence and asks the router
#: to find the record from the REST of its text. For a skill that is fine -- the body and
#: headings remain. For an `mcp` record the description IS essentially the whole text, so
#: the holdout left ~10 tokens (a server name and an argv) and the gold record fell to rank
#: 41-284 with a score of 0.014-0.095. Those four queries were scored as router failures
#: and dragged L1 gold-hit@5 from 0.750 to 0.656.
#:
#: That is a defect in the EXPERIMENT, not in the router: no matcher can recover a record
#: from text that was deleted. Excluding them is therefore a correction, not a convenience
#: -- and the exclusions are COUNTED and reported (`QuerySet.excluded_unanswerable`) rather
#: than quietly dropped, because "we removed the queries we failed" and "we removed the
#: queries that were impossible" look identical unless the count and reason are published.
L1_MIN_RESIDUAL_TOKENS = 25


def _residual_tokens(rec, holdout: str) -> int:
    """Distinct content tokens left in `rec.routing_text` once `holdout` is removed."""
    remaining = rec.routing_text.replace(holdout, " ")
    cleaned = _clean_trigger(holdout)
    if cleaned:
        remaining = remaining.replace(cleaned, " ")
    return len(set(tokens(remaining)))


def generate_l1(
    idx: Index, per_class: int = 4, seed_classes: tuple[str, ...] = ()
) -> list[Query]:
    """Mechanically derive held-out queries from the index, per capability class.

    Deterministic: capabilities are visited in the index's own sorted order and the
    FIRST qualifying holdout is taken, so the generated set is stable across runs without
    needing a random seed (a seeded shuffle would still churn whenever the inventory
    changes, which would make regression comparisons meaningless).
    """
    classes = seed_classes or (
        "skill",
        "workflow",
        "protocol",
        "preset",
        "candidate",
        "mcp",
        "command",
        "agent",
    )
    out: list[Query] = []
    per: dict[str, int] = {}
    excluded: list[str] = []
    for r in idx.records:
        if r.cls not in classes or per.get(r.cls, 0) >= per_class:
            continue
        opts = _candidate_holdouts(r)
        if not opts:
            continue
        # Take the first holdout that leaves the record findable at all.
        pick = None
        for sub, raw, text in opts:
            residual = _residual_tokens(r, raw)
            if residual >= L1_MIN_RESIDUAL_TOKENS:
                pick = (sub, raw, text)
                break
            excluded.append(
                f"{r.id} ({sub}): only {residual} tokens survive the holdout"
            )
        if pick is None:
            continue
        sub, raw, text = pick
        per[r.cls] = per.get(r.cls, 0) + 1
        out.append(
            Query(
                qid=f"{sub}-{r.cls}-{per[r.cls]:02d}",
                text=text,
                gold=frozenset({r.id}),
                tier="L1",
                note=(
                    "mechanically derived from the capability's own "
                    + ("declared trigger" if sub == "L1a" else "declared description")
                    + "; that text is WITHHELD from routing_text during evaluation"
                ),
                holdout_id=r.id,
                holdout_text=raw,
            )
        )
    generate_l1.excluded_unanswerable = excluded  # type: ignore[attr-defined]
    return out


def holdout_index(idx: Index, queries: list[Query]) -> Index:
    """Deep-copy `idx` with every L1 query's trigger sentence stripped from its record.

    This is what makes L1 a real test. Implemented as a COPY, never in place: mutating
    the shared index would silently contaminate every later evaluation in the same
    process -- the same class of defect as D3's test that mutated the tree it measured.
    """
    clone = copy.deepcopy(idx)
    by_id = {r.id: r for r in clone.records}
    for q in queries:
        if q.tier != "L1" or not q.holdout_id:
            continue
        rec = by_id.get(q.holdout_id)
        if rec is None:  # pragma: no cover - ids come from this same index
            continue
        for frag in {q.holdout_text, _clean_trigger(q.holdout_text)}:
            if frag:
                rec.routing_text = rec.routing_text.replace(frag, " ")
        rec.triggers = tuple(t for t in rec.triggers if t != q.holdout_text)
        rec.routing_text = re.sub(r"\s+", " ", rec.routing_text).strip()
    return clone


# ------------------------------------------------------------------- L2/L3/L4 (authored)
#
# Gold ids below were each verified to EXIST in the live index before being written
# down (`_verify_gold_ids` asserts it, so a renamed capability breaks the test rather
# than silently scoring zero -- an unresolvable gold id is indistinguishable from a
# router failure otherwise, and would be charged to the router).

L2: tuple[Query, ...] = (
    Query(
        "L2-01",
        "turn my horizontal footage into something that fills a phone screen",
        frozenset({"skill:reframe", "skill:video-resize-aspect"}),
        "L2",
        "no shared term with 9:16/vertical/portrait vocabulary in the query",
    ),
    Query(
        "L2-02",
        "there is a broadcaster bug in the corner of every frame and I want it gone cleanly",
        frozenset({"skill:video-watermark-removal"}),
        "L2",
        "'broadcaster bug' instead of watermark/logo",
    ),
    Query(
        "L2-03",
        "strip out the long gaps where nobody is talking",
        frozenset({"skill:silence-trim"}),
        "L2",
    ),
    Query(
        "L2-04",
        "put the words on screen so they pop one at a time like the viral edits",
        frozenset({"skill:caption-burn"}),
        "L2",
        "karaoke captions described indirectly",
    ),
    Query(
        "L2-05",
        "re-voice this in Spanish but keep it sounding like the same person",
        frozenset({"skill:media-dub"}),
        "L2",
    ),
    Query(
        "L2-06",
        "everyone on the panel nodded along immediately and no one pushed back",
        frozenset(
            {
                "protocol:p25-blind-reevaluation",
                "protocol:p12-adversarial-collaboration",
            }
        ),
        "L2",
        "premature-convergence / echo-chamber described in plain words",
    ),
    Query(
        "L2-07",
        "my installer clobbered newer files that only existed on the machine",
        frozenset({"workflow:anchor-checked-per-file-deploy"}),
        "L2",
    ),
    Query(
        "L2-08",
        "I keep believing a number I never actually measured",
        frozenset({"skill:fresh-context-verify"}),
        "L2",
    ),
    Query(
        "L2-09",
        "prove this cleanup did not change what the function does",
        frozenset({"skill:refactor-equivalence"}),
        "L2",
    ),
    Query(
        "L2-10",
        "the built app ships but does it actually work when installed",
        frozenset({"skill:packaged-artifact-smoke"}),
        "L2",
    ),
    Query(
        "L2-11",
        "which of these competing patches should I actually keep",
        frozenset({"skill:execution-grounded-bon"}),
        "L2",
    ),
    Query(
        "L2-12",
        "the buttons look fine but the colours are unreadable for some people",
        frozenset({"skill:ui-audit"}),
        "L2",
    ),
    Query(
        "L2-13",
        "rent something with a big graphics card for a few hours",
        frozenset({"skill:cloud-infra-toolchain"}),
        "L2",
    ),
    Query(
        "L2-14",
        "find the function again after the library was rebuilt and everything moved",
        frozenset({"skill:bc-update-survival", "skill:ida-multi-mcp"}),
        "L2",
    ),
    Query(
        "L2-15",
        "run many independent jobs at once across separate checkouts",
        frozenset(
            {"skill:orchestration-patterns", "skill:dispatching-parallel-agents"}
        ),
        "L2",
        "both gold ids are legitimate; a single-answer metric would mis-score this",
    ),
    Query(
        "L2-16",
        "I need the smallest check that would still catch this change",
        frozenset({"skill:smallest-check-ladder"}),
        "L2",
    ),
    Query(
        "L2-17",
        "score how good this interface looks against real design rules",
        frozenset({"skill:ui-audit", "skill:design-system"}),
        "L2",
    ),
    Query(
        "L2-18",
        "get me clean text out of a research article with the page it came from",
        frozenset({"skill:pdf-reader"}),
        "L2",
    ),
    # --- MCP tool-family queries -------------------------------------------------------
    # Added because excluding the unanswerable L1b/mcp queries (see L1_MIN_RESIDUAL_TOKENS)
    # left the `mcp` class with ZERO coverage, and an unmeasured class is not the same as a
    # working one. These are author-labelled like the rest of L2 and carry the same leakage
    # meter. Gold sets include the same-named SKILL where one exists, because a skill that
    # documents a server and the server itself are both legitimate answers -- deciding
    # between them is not something this query set has the authority to arbitrate.
    Query(
        "L2-19",
        "I need to drive a real Chrome window that is already logged in and click "
        "through a page",
        frozenset({"mcp:playwright-cdp", "mcp:playwright-extension", "skill:ui-drive"}),
        "L2",
        "browser-rail selection; the CDP and extension rails are both defensible",
    ),
    Query(
        "L2-20",
        "spin up a rented GPU box for a few hours and copy my data onto it",
        frozenset({"mcp:cloud-hub", "skill:cloud-infra-toolchain"}),
        "L2",
    ),
    Query(
        "L2-21",
        "symbolically explore a stripped native executable and get its control flow "
        "graph",
        frozenset({"mcp:angr", "skill:game-re-binary"}),
        "L2",
    ),
)

L3: tuple[Query, ...] = (
    Query(
        "L3-01",
        "what is the capital of Mongolia and how many people live there",
        frozenset(),
        "L3",
        "general knowledge; no capability should fire",
    ),
    Query(
        "L3-02",
        "please book me a dentist appointment for next Tuesday afternoon",
        frozenset(),
        "L3",
        "real-world action outside every capability",
    ),
    Query(
        "L3-03",
        "my houseplant leaves are turning yellow at the edges",
        frozenset(),
        "L3",
    ),
    Query(
        "L3-04",
        "translate this sentence into French for a birthday card",
        frozenset(),
        "L3",
        "plain LLM task; no tool needed",
    ),
    Query(
        "L3-05",
        "what did I have for lunch yesterday",
        frozenset(),
        "L3",
        "unanswerable; must not hallucinate a capability",
    ),
    Query(
        "L3-06",
        "recommend a good pair of running shoes under a hundred euros",
        frozenset(),
        "L3",
    ),
)

L4: tuple[Query, ...] = (
    Query(
        "L4-01",
        "I want a structured multi-agent review where the reviewers are forced to disagree "
        "and the dissent is preserved in the record",
        frozenset(
            {
                "protocol:p12-adversarial-collaboration",
                "protocol:p08-red-blue-team",
                "protocol:p25-blind-reevaluation",
            }
        ),
        "L4",
        "several council protocols are legitimately relevant",
    ),
    Query(
        "L4-02",
        "a workflow for landing harness changes into the live tree without losing work",
        frozenset(
            {
                "workflow:anchor-checked-per-file-deploy",
                "workflow:dual-tree-plumbing-mirror",
            }
        ),
        "L4",
    ),
    Query(
        "L4-03",
        "everything I need to take a long horizontal interview and ship vertical clips with captions",
        frozenset(
            {
                "skill:reframe",
                "skill:reframe-video-cutting",
                "skill:caption-burn",
                "skill:silence-trim",
            }
        ),
        "L4",
        "genuine multi-capability pipeline request",
    ),
    Query(
        "L4-04",
        "verify a claim two independent ways before I act on it",
        frozenset(
            {
                "skill:fresh-context-verify",
                "skill:diff-blind-test-synth",
                "skill:agent-as-judge",
            }
        ),
        "L4",
    ),
    Query(
        "L4-05",
        "reverse engineer a stripped native library and check the decompilation is right",
        frozenset(
            {
                "skill:llm-decompile-verify",
                "skill:game-re-binary",
                "skill:ghidra-mcp",
                "skill:radare2",
            }
        ),
        "L4",
    ),
)


@dataclass
class QuerySet:
    queries: list[Query] = field(default_factory=list)
    unresolved_gold: list[str] = field(default_factory=list)
    #: L1 candidates rejected because the holdout would leave the record unfindable.
    #: Published, not silent -- see L1_MIN_RESIDUAL_TOKENS.
    excluded_unanswerable: list[str] = field(default_factory=list)

    def by_tier(self, tier: str) -> list[Query]:
        return [q for q in self.queries if q.tier == tier]

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for q in self.queries:
            out[q.tier] = out.get(q.tier, 0) + 1
        return out


def lexical_overlap(query: str, idx: Index, gold: frozenset[str]) -> float:
    """Jaccard overlap between the query's content tokens and the gold records' OWN
    declared descriptions (`desc_source`, NOT the enriched routing_text).

    This is the leakage meter for author-labelled tiers. Reported, never acted on --
    suppressing high-overlap queries would be tuning the test set to flatter the router.
    """
    q = set(tokens(query))
    if not q or not gold:
        return 0.0
    by_id = idx.by_id()
    g: set[str] = set()
    for gid in gold:
        rec = by_id.get(gid)
        if rec is not None:
            g |= set(tokens(rec.desc_source))
    if not g:
        return 0.0
    return len(q & g) / len(q | g)


def build(idx: Index, *, l1_per_class: int = 4) -> QuerySet:
    """Assemble the full labelled set and resolve every authored gold id.

    An authored gold id that does not exist in the index is reported in
    `unresolved_gold` and the query is DROPPED. Keeping it would charge a renamed or
    missing capability to the router as a recall failure -- attributing an inventory
    change to a routing regression.
    """
    qs: list[Query] = list(generate_l1(idx, per_class=l1_per_class))
    known = set(idx.by_id())
    unresolved: list[str] = []
    for q in (*L2, *L3, *L4):
        missing = sorted(g for g in q.gold if g not in known)
        if missing:
            unresolved.extend(f"{q.qid}:{m}" for m in missing)
            kept = frozenset(g for g in q.gold if g in known)
            if not kept and q.tier != "L3":
                continue
            q = Query(
                q.qid, q.text, kept, q.tier, q.note + " [gold pruned: unresolved id]"
            )
        qs.append(q)
    return QuerySet(
        queries=qs,
        unresolved_gold=unresolved,
        excluded_unanswerable=list(getattr(generate_l1, "excluded_unanswerable", [])),
    )


#: Convenience for callers that only need the texts (e.g. `budget.measure`). Built
#: lazily by `build()`; this module deliberately exposes no import-time index walk.
LABELLED: list[Query] = []


def load(idx: Index | None = None) -> QuerySet:
    """Build (and memoize into `LABELLED`) the labelled set for `idx`."""
    from .index import discover

    qset = build(idx if idx is not None else discover())
    LABELLED.clear()
    LABELLED.extend(qset.queries)
    return qset


def main(argv: list[str] | None = None) -> int:
    import sys

    from .index import discover

    argv = list(sys.argv[1:] if argv is None else argv)
    idx = discover()
    qset = build(idx)
    payload = {
        "counts": qset.counts(),
        "total": len(qset.queries),
        "unresolved_gold": qset.unresolved_gold,
        "excluded_unanswerable_count": len(qset.excluded_unanswerable),
        "excluded_unanswerable": qset.excluded_unanswerable,
        "lexical_overlap_by_tier": {},
    }
    for tier in ("L1", "L2", "L4"):
        ov = [lexical_overlap(q.text, idx, q.gold) for q in qset.by_tier(tier)]
        if ov:
            payload["lexical_overlap_by_tier"][tier] = {
                "mean": round(sum(ov) / len(ov), 4),
                "max": round(max(ov), 4),
            }
    if "--dump" in argv:
        payload["queries"] = [q.as_dict() for q in qset.queries]
    print(json.dumps(payload, indent=2))
    if qset.unresolved_gold:
        print(f"FAILED:routing-queries unresolved-gold={len(qset.unresolved_gold)}")
        return 1
    if len(qset.queries) < 40:
        print(f"FAILED:routing-queries too-few={len(qset.queries)}")
        return 1
    print(f"SUCCESS:routing-queries n={len(qset.queries)}")
    return 0
