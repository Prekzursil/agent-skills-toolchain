#!/usr/bin/env python
"""WAVE 4 - INDEPENDENT re-measurement of Phase 8 routing (`platform/routing/`).

WHY THIS FILE EXISTS
--------------------
The Wave-3 floor audit's routing probe crashed, so Phase 8's precision, recall and
bytes-per-query were the LANE'S OWN self-report with nothing checking them. The crash
named in the hand-off was:

    AttributeError: type object 'SemanticModel' has no attribute 'build'

and it is reproduced as `stage0` below, both states: the broken call must raise and the
real constructor must succeed. `semantic.SemanticModel` exposes `fit`, not `build`
(`platform/routing/semantic.py:211`); `Router.build` DOES exist
(`platform/routing/router.py:279`) and is what a caller should use.

WHAT MAKES THIS INDEPENDENT (and what does not)
-----------------------------------------------
Independent:
  * bytes are counted by THIS file (`len("\\n".join(cap.card).encode())`), never by
    `budget.measure`. Every count is cross-checked against `Decision.injected_bytes` so a
    disagreement in the headline cannot be a definitional artifact - `stage5` asserts
    equality on every single decision and reports the count of agreements.
  * precision / recall / gold-hit are computed here, not by `metrics.evaluate`.
  * the held-out index is rebuilt by THIS file (`my_holdout`), with a POSITIVE assertion
    that the held-out sentence is really gone from the record's routing_text.
  * TWO further query sets are built here (`QS-B` mechanical, `QS-C` authored), so the
    lane's 60-query set is one signal of three rather than the only one.
  * a metric the lane does NOT report at all: BYTES PER CORRECT SELECTION, which is what
    separates "recall rose because matching improved" from "recall rose because more was
    injected".

NOT independent, stated inline so it is not mistaken for more than it is:
  * the corpus, the router and the tokenizer under test are the lane's own code - this is
    a re-measurement of that router, not a reimplementation of routing.
  * `descriptions.tokens` is reused for the residual-token check and the leakage meter.
    Those are corpus-vocabulary questions, not scoring questions, and using a different
    tokenizer would make the numbers non-comparable to the lane's.
  * QS-C is AUTHOR-LABELLED BY AN AGENT THAT HAD ALREADY READ `router.py` AND
    `semantic.py`. That is a real leakage risk (I know the mechanism I am testing), so
    every QS-C query carries the same Jaccard leakage meter the lane uses, and the
    settling experiment for a genuinely blind set is stated in the report.

READ THE CONTROLS BEFORE THE HEADLINE. `stage6` runs four selectors through the exact
same accounting: the real router, a flood-everything router, a query-blind top-k router,
and a gold ORACLE. Without them "good recall at low bytes" has no counterfactual.
"""

from __future__ import annotations

import copy
import json
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
BUILD = HERE.parent / "platform"
OUT = HERE / "WAVE4-ROUTING-PROBE.json"
LANE_MEASUREMENTS = BUILD / "routing" / "MEASUREMENTS.json"

sys.path.insert(0, str(BUILD))

KS = (1, 3, 5, 10)

REPORT: dict[str, Any] = {
    "unit": "close/audit-probe-repair",
    "artifact": str(OUT),
    "status": "RUNNING - every stage below is UNKNOWN until it is written",
    "stages": {},
}


def flush() -> None:
    """Rewrite the artifact after every milestone. Whatever is on disk is truthful."""
    blob = json.dumps(REPORT, indent=2, ensure_ascii=False) + "\n"
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        fh.write(blob)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ===================================================================== stage 0: crash


def stage0_crash_repro(full: Any) -> dict[str, Any]:
    """BOTH-STATES reproduction of the reported crash.

    A fix is only verified if the broken form still fails and the fixed form works. A
    probe that is silent in both states measures nothing.
    """
    from routing import index as ridx
    from routing import router as rr
    from routing import semantic as rsem

    broken_err = None
    try:
        rsem.SemanticModel.build  # noqa: B018 - deliberate attribute probe
        broken_raised = False
    except AttributeError as e:
        broken_raised = True
        broken_err = f"{type(e).__name__}: {e}"

    recs = list(full.records[:40])
    counts: dict[str, int] = {}
    for r in recs:
        counts[r.cls] = counts.get(r.cls, 0) + 1
    tiny = ridx.Index(records=recs, counts=counts, roots=full.roots)
    fixed_ok, fixed_err, n_ids = False, None, 0
    try:
        m = rsem.SemanticModel.fit(tiny)
        n_ids = len(m.ids)
        fixed_ok = n_ids == 40
    except Exception as e:  # pragma: no cover - would itself be the finding
        fixed_err = f"{type(e).__name__}: {e}"

    return {
        "reported_crash": "AttributeError: type object 'SemanticModel' has no attribute 'build'",
        "BROKEN_STATE_call": "semantic.SemanticModel.build",
        "BROKEN_STATE_raised": broken_raised,
        "BROKEN_STATE_error": broken_err,
        "FIXED_STATE_call": "semantic.SemanticModel.fit(idx) -> SemanticModel",
        "FIXED_STATE_ok": fixed_ok,
        "FIXED_STATE_error": fixed_err,
        "FIXED_STATE_fitted_records": n_ids,
        "real_constructor_anchor": "platform/routing/semantic.py:211 @classmethod fit",
        "router_constructor_anchor": "platform/routing/router.py:279 @classmethod build",
        "note": "Router.build DOES exist; only SemanticModel.build does not. A probe that "
        "reached for SemanticModel.build was calling the wrong class's factory.",
        "both_states_valid": broken_raised and fixed_ok,
        "public_attrs_on_SemanticModel": sorted(
            a for a in dir(rsem.SemanticModel) if not a.startswith("_")
        ),
        "public_classmethods_on_Router": sorted(
            a for a in dir(rr.Router) if not a.startswith("_")
        ),
    }


# ============================================================= holdout (reimplemented)


def my_holdout(idx: Any, holdouts: list[tuple[str, str]]) -> tuple[Any, dict[str, Any]]:
    """Deep-copy `idx` and strip each (record_id, sentence) pair from routing_text.

    POSITIVE assertion, not "nothing went wrong": every requested strip must be verified
    absent afterwards, and the count of verified strips is reported. A holdout that
    silently failed would turn a retrieval test into a string-equality test - the exact
    circularity the lane's own docstring warns about
    (`platform/routing/queries.py:9`).
    """
    clone = copy.deepcopy(idx)
    by_id = {r.id: r for r in clone.records}
    verified, failed, missing = 0, [], []
    for rid, sent in holdouts:
        rec = by_id.get(rid)
        if rec is None:
            missing.append(rid)
            continue
        cleaned = re.sub(r"\s+", " ", sent).strip(" .,;:-")
        for frag in {sent, cleaned}:
            if frag:
                rec.routing_text = rec.routing_text.replace(frag, " ")
        rec.triggers = tuple(t for t in rec.triggers if t != sent)
        rec.routing_text = re.sub(r"\s+", " ", rec.routing_text).strip()
        if cleaned and cleaned.lower() in rec.routing_text.lower():
            failed.append(rid)
        else:
            verified += 1
    return clone, {
        "requested": len(holdouts),
        "verified_absent_after_strip": verified,
        "STILL_PRESENT_after_strip": failed,
        "unknown_ids": missing,
        "all_verified": verified == len(holdouts) and not failed and not missing,
    }


# ============================================================ query sets B (mechanical)


def build_qs_b(
    idx: Any, exclude: set[str], *, stride: int = 13, cap: int = 60
) -> list[dict]:
    """MECHANICAL leave-one-out set over a stride sample DISJOINT from the lane's.

    Same protocol as the lane's L1 (hold out one declared sentence, ask the router to
    find the record from what is left), but over different records. That is the point:
    if the lane's L1 number came from a lucky first-four-per-class it will not survive a
    different sample of the same corpus. No author judgement enters a label here.
    """
    from routing.descriptions import tokens

    out: list[dict] = []
    for i, r in enumerate(idx.records):
        if i % stride or r.id in exclude:
            continue
        src = (r.desc_source or "").strip()
        if not src:
            continue
        for sent in re.split(r"(?<=[.;])\s+", src):
            t = re.sub(r"\s+", " ", sent).strip(" .,;:-")
            if not (40 <= len(t) <= 220):
                continue
            if r.name.lower() in t.lower():
                continue
            residual = r.routing_text.replace(sent, " ")
            cleaned = re.sub(r"\s+", " ", sent).strip(" .,;:-")
            residual = residual.replace(cleaned, " ")
            n_resid = len(set(tokens(residual)))
            if n_resid < 25:
                # Unanswerable by construction; excluded and COUNTED, never silent.
                out.append(
                    {
                        "qid": f"B-EXCLUDED-{r.id}",
                        "excluded": True,
                        "reason": f"only {n_resid} tokens survive the holdout",
                        "text": t,
                        "gold": [],
                        "holdout": (r.id, sent),
                    }
                )
                break
            out.append(
                {
                    "qid": f"B-{r.cls}-{len(out):03d}",
                    "text": t,
                    "gold": [r.id],
                    "tier": "B-mech-leave-one-out",
                    "holdout": (r.id, sent),
                }
            )
            break
        if len([q for q in out if not q.get("excluded")]) >= cap:
            break
    return out


# ============================================================== query set C (authored)
#
# LABELLING PROTOCOL, stated so it can be discounted rather than trusted:
#   * Every gold id was chosen FIRST from a deterministic stride walk of the index
#     (`wave4_index_dump.py`) restricted to records that are NOT in any lane gold set and
#     NOT any lane holdout source. So the lane's own 60 queries cannot overlap this set.
#   * The query text was then written in plain user voice from the record's PURPOSE, with
#     a deliberate effort to avoid the record's own distinctive vocabulary. `leakage`
#     (Jaccard of query tokens vs the gold record's declared description) is computed and
#     REPORTED for every one; it is never used to filter, because dropping high-overlap
#     queries would be tuning the test set to flatter the router.
#   * Multi-gold entries are used only where two records are both genuinely correct.
#   * Negatives (gold = []) are everyday requests no capability in this inventory should
#     answer. They score ABSTENTION, not precision.
#   * DISCLOSED WEAKNESS: the author had already read `router.py` and `semantic.py`. A
#     truly blind set would be authored by someone who has not. Settling experiment:
#     re-author QS-C from the class/name list alone with the router source unread, and
#     compare gold-hit@5.

QS_C: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "make this endpoint quicker - try a pile of variants and keep whichever one measures fastest",
        ("skill:benchmark-optimization-loop",),
    ),
    (
        "farm several coding jobs out to separate checkouts at once and let me watch how each is doing",
        ("skill:claude-devfleet",),
    ),
    (
        "set me up a scratch pad where I can run bits of python against this data and keep the output",
        ("skill:jupyter-notebook",),
    ),
    (
        "get the other vendor's assistant on this machine talking to you so the two of you can split the work",
        ("skill:multi-ai-mingle",),
    ),
    (
        "walk through the signup form in a real browser and grab a picture at each step",
        ("skill:playwright",),
    ),
    (
        "look up an attack technique in the reference material I keep on this box, no internet",
        ("skill:security-kb-lookup",),
    ),
    (
        "hand every independent piece to a fresh helper and check its work before accepting it",
        ("skill:subagent-driven-development",),
    ),
    (
        "I want to add a new capability document and be sure it actually works before it ships",
        ("skill:writing-skills",),
    ),
    (
        "are the other command-line assistants installed and pointed at the right config",
        ("command:external-tools-health",),
    ),
    (
        "find handlers that are wired up but can never actually fire",
        ("workflow:silent-disarm-hunt",),
    ),
    (
        "nothing gets published until somebody has measured what it costs to keep loaded",
        ("workflow:marketplace-publication-governance",),
    ),
    (
        "list out every option first and have people rank them on their own before anyone argues",
        ("protocol:p06-nominal-group-technique",),
    ),
    (
        "I want a resolution that makes one side better without making the other side worse - no splitting the difference",
        ("protocol:p29-triz-contradiction",),
    ),
    (
        "when a saved note goes out of date, point the old one at the replacement and date the new one",
        ("preset:c-h62-memory-note-supersession",),
    ),
    (
        "pull the colours and a picture of one frame out of my design file",
        ("mcp:figma",),
    ),
    (
        "break this feature into phases and dependencies before anybody writes code",
        ("agent:planner",),
    ),
    ("scan the code that was just generated for security holes", ("plugin:semgrep",)),
    (
        "go wide and tell me what my toolkit is missing compared with other setups",
        ("skill:gem-hunt",),
    ),
    (
        "pull the compounds and protein targets out of this article so I can feed the chemistry tools",
        ("skill:drug-discovery-literature-bridge",),
    ),
    (
        "we have an ancient monolith to drag into this decade",
        ("plugin:code-modernization",),
    ),
    (
        "give the reviewers each other's whole write-up, not a summary of it",
        ("workflow:bp-cnc-04-full-text-adversarial-sibling-review",),
    ),
    (
        "explore the question from six different mindsets, one at a time",
        ("preset:c-s21-six-hats-6",),
    ),
    # --- negatives: no capability in this inventory legitimately answers these ---
    ("how do I get red wine out of a wool carpet", ()),
    ("what year did the bridge at Cernavoda open", ()),
    ("my cat keeps knocking things off the counter at four in the morning", ()),
    ("convert two hundred and fifty grams of flour into cups", ()),
    ("which train goes from Bucharest to Brasov on Sunday morning", ()),
    ("remind me to call my mother on Thursday", ()),
)


def build_qs_c(idx: Any) -> tuple[list[dict], list[str]]:
    """Resolve every authored gold id against the live index. Unresolved ids are a
    FINDING, not a silent zero - charging a renamed capability to the router as a recall
    miss would attribute an inventory change to a routing regression."""
    known = set(idx.by_id())
    rows, unresolved = [], []
    for i, (text, gold) in enumerate(QS_C, 1):
        missing = [g for g in gold if g not in known]
        unresolved.extend(missing)
        rows.append(
            {
                "qid": f"C-{i:02d}",
                "text": text,
                "gold": [g for g in gold if g in known],
                "tier": "C-authored-paraphrase" if gold else "C-negative",
                "unresolved_gold": missing,
            }
        )
    return rows, unresolved


# ================================================================== leakage meter (mine)


def leakage(text: str, idx: Any, gold: list[str]) -> float:
    """Jaccard of query content tokens against the gold records' DECLARED descriptions."""
    from routing.descriptions import tokens

    q = set(tokens(text))
    if not q or not gold:
        return 0.0
    by_id = idx.by_id()
    g: set[str] = set()
    for gid in gold:
        rec = by_id.get(gid)
        if rec is not None:
            g |= set(tokens(rec.desc_source))
    return round(len(q & g) / len(q | g), 4) if g else 0.0


# ======================================================================= the measurement

BYTE_XCHECK = {"agree": 0, "disagree": []}


def _card_bytes(caps: list[Any]) -> int:
    return len("\n".join(c.card for c in caps).encode("utf-8"))


def _full_bytes(caps: list[Any]) -> int:
    return len(
        "\n".join(f"{c.invoke} - {c.routing_text}" for c in caps).encode("utf-8")
    )


def measure(
    select: Callable[[str, int], list[Any]],
    rows: list[dict],
    *,
    fits: Callable[[str, int], bool] | None = None,
    ks: tuple[int, ...] = KS,
) -> dict[str, Any]:
    """Bytes, precision, recall and BYTES-PER-CORRECT-SELECTION for one selector.

    `select(query, k) -> [Capability]` is the seam, so the real router, a flood router, a
    query-blind router and a gold oracle all go through identical accounting.
    """
    pos = [r for r in rows if r["gold"]]
    neg = [r for r in rows if not r["gold"]]
    per_k: dict[str, Any] = {}
    for k in ks:
        card_all = full_all = items_all = 0
        peak = 0
        card_pos = 0
        correct = 0
        selected_total = 0
        prec, rec, hits = [], [], []
        misses: list[dict] = []
        for r in rows:
            caps = select(r["text"], k)
            cb, fb = _card_bytes(caps), _full_bytes(caps)
            card_all += cb
            full_all += fb
            peak = max(peak, cb)
            items_all += len(caps)
            ids = [c.id for c in caps]
            if r["gold"]:
                card_pos += cb
                gold = set(r["gold"])
                hit = len([i for i in ids if i in gold])
                correct += hit
                selected_total += len(ids)
                prec.append(hit / len(ids) if ids else 0.0)
                rec.append(hit / len(gold))
                hits.append(1.0 if hit else 0.0)
                if k == max(ks) and not hit:
                    misses.append(
                        {
                            "qid": r["qid"],
                            "query": r["text"][:80],
                            "gold": r["gold"],
                            "got": ids[:5],
                        }
                    )
        nq = max(len(rows), 1)
        npos = max(len(pos), 1)
        per_k[str(k)] = {
            "mean_card_bytes_per_query_ALL": round(card_all / nq, 1),
            "mean_card_bytes_per_query_GOLD_BEARING_ONLY": round(card_pos / npos, 1),
            "peak_card_bytes": peak,
            "mean_full_description_bytes_per_query_ALL": round(full_all / nq, 1),
            "card_saving_ratio_vs_full_description": round(full_all / card_all, 2)
            if card_all
            else None,
            "mean_items_returned": round(items_all / nq, 2),
            "precision": round(sum(prec) / npos, 4) if prec else None,
            "recall": round(sum(rec) / npos, 4) if rec else None,
            "gold_hit_rate": round(sum(hits) / npos, 4) if hits else None,
            "correct_selections_total": correct,
            "selections_total_on_gold_bearing": selected_total,
            "wasted_selections": selected_total - correct,
            "BYTES_PER_CORRECT_SELECTION": round(card_pos / correct, 1)
            if correct
            else None,
            "total_card_bytes_on_gold_bearing": card_pos,
            "misses_at_max_k": misses[:12],
        }
    # marginal cost of the extra recall each k step buys
    marg = {}
    ladder = [str(k) for k in ks]
    for a, b in zip(ladder, ladder[1:]):
        d_bytes = (
            per_k[b]["total_card_bytes_on_gold_bearing"]
            - per_k[a]["total_card_bytes_on_gold_bearing"]
        )
        d_corr = (
            per_k[b]["correct_selections_total"] - per_k[a]["correct_selections_total"]
        )
        marg[f"k={a}->{b}"] = {
            "extra_card_bytes": d_bytes,
            "extra_correct_selections": d_corr,
            "MARGINAL_BYTES_PER_EXTRA_CORRECT": round(d_bytes / d_corr, 1)
            if d_corr
            else None,
            "recall_delta": round(
                (per_k[b]["recall"] or 0) - (per_k[a]["recall"] or 0), 4
            ),
        }
    out: dict[str, Any] = {
        "n_queries": len(rows),
        "n_gold_bearing": len(pos),
        "n_negative": len(neg),
        "per_k": per_k,
        "marginal": marg,
    }
    if neg and fits is not None:
        ab = [1.0 if not fits(r["text"], max(ks)) else 0.0 for r in neg]
        fired = [
            {
                "qid": r["qid"],
                "query": r["text"][:70],
                "got": [c.id for c in select(r["text"], max(ks))][:3],
            }
            for r in neg
            if fits(r["text"], max(ks))
        ]
        out["negatives"] = {
            "n": len(neg),
            "abstained": int(sum(ab)),
            "abstain_rate": round(sum(ab) / len(neg), 4),
            "false_fires": fired,
        }
    return out


def router_selector(router: Any) -> Callable[[str, int], list[Any]]:
    def sel(q: str, k: int) -> list[Any]:
        d = router.route(q, k=k)
        caps = [c for c, _s in d.selected]
        mine = _card_bytes(caps)
        if mine == d.injected_bytes:
            BYTE_XCHECK["agree"] += 1
        else:
            BYTE_XCHECK["disagree"].append(
                {"query": q[:50], "k": k, "mine": mine, "lane": d.injected_bytes}
            )
        return caps

    return sel


# ============================================================================== driver


def main() -> int:
    t0 = time.time()

    from routing import index as ridx
    from routing import queries as rq
    from routing.router import Router

    log("stage1: discover index + lane query set")
    raw = ridx.discover()

    log("stage0: crash reproduction")
    REPORT["stages"]["stage0_crash_repro"] = stage0_crash_repro(raw)
    flush()
    lane_qs = rq.build(raw)
    lane_rows = [
        {
            "qid": q.qid,
            "text": q.text,
            "gold": sorted(q.gold),
            "tier": q.tier,
            "holdout": (q.holdout_id, q.holdout_text) if q.holdout_id else None,
        }
        for q in lane_qs.queries
    ]
    lane_ids = {r["gold"][i] for r in lane_rows for i in range(len(r["gold"]))}
    lane_ids |= {r["holdout"][0] for r in lane_rows if r["holdout"]}
    REPORT["stages"]["stage1_index"] = {
        "index_total": len(raw.records),
        "counts": dict(sorted(raw.counts.items())),
        "lane_query_total": len(lane_rows),
        "lane_tiers": lane_qs.counts(),
        "lane_unresolved_gold": lane_qs.unresolved_gold,
        "lane_excluded_unanswerable": len(lane_qs.excluded_unanswerable),
        "lane_gold_or_holdout_ids": len(lane_ids),
    }
    flush()

    log("stage2: build routers (raw, lane-holdout)")
    r_raw = Router.build(copy.deepcopy(raw))
    lane_holdouts = [
        (r["holdout"][0], r["holdout"][1]) for r in lane_rows if r["holdout"]
    ]
    held_lane, hl_stats = my_holdout(raw, lane_holdouts)
    r_lane = Router.build(copy.deepcopy(held_lane))
    REPORT["stages"]["stage2_holdout"] = {
        "lane_holdout_verification": hl_stats,
        "why": "L1 is only a retrieval test if the query sentence is absent from the "
        "record it must retrieve. Measuring on the RAW index instead makes L1 circular "
        "- which is exactly what the crashed Wave-3 probe did (Router.build(inv)).",
    }
    flush()

    log("stage3: build QS-B (mechanical, disjoint sample)")
    qs_b_all = build_qs_b(raw, lane_ids)
    qs_b = [q for q in qs_b_all if not q.get("excluded")]
    qs_b_excl = [q for q in qs_b_all if q.get("excluded")]
    b_holdouts = [tuple(q["holdout"]) for q in qs_b]
    held_b, hb_stats = my_holdout(raw, b_holdouts)  # type: ignore[arg-type]
    r_b = Router.build(copy.deepcopy(held_b))
    REPORT["stages"]["stage3_qs_b"] = {
        "protocol": "mechanical leave-one-out over a stride-13 walk of the index, "
        "restricted to records that are NOT in any lane gold set and NOT a lane holdout "
        "source; the held-out sentence is stripped from routing_text before the router is "
        "built, and the strip is positively verified",
        "n_queries": len(qs_b),
        "n_excluded_unanswerable": len(qs_b_excl),
        "excluded": [{"qid": q["qid"], "reason": q["reason"]} for q in qs_b_excl],
        "by_class": {},
        "holdout_verification": hb_stats,
        "disjoint_from_lane_gold": not ({q["gold"][0] for q in qs_b} & lane_ids),
    }
    bc: dict[str, int] = {}
    for q in qs_b:
        c = q["gold"][0].split(":", 1)[0]
        bc[c] = bc.get(c, 0) + 1
    REPORT["stages"]["stage3_qs_b"]["by_class"] = dict(sorted(bc.items()))
    flush()

    log("stage4: build QS-C (authored)")
    qs_c, unresolved_c = build_qs_c(raw)
    for q in qs_c:
        q["leakage_jaccard_vs_gold_description"] = leakage(q["text"], raw, q["gold"])
    pos_c = [q for q in qs_c if q["gold"]]
    REPORT["stages"]["stage4_qs_c"] = {
        "n_queries": len(qs_c),
        "n_positive": len(pos_c),
        "n_negative": len(qs_c) - len(pos_c),
        "unresolved_gold": unresolved_c,
        "mean_leakage": round(
            sum(q["leakage_jaccard_vs_gold_description"] for q in pos_c)
            / max(1, len(pos_c)),
            4,
        ),
        "max_leakage": max(
            (q["leakage_jaccard_vs_gold_description"] for q in pos_c), default=0.0
        ),
        "lane_L2_mean_leakage_for_comparison": 0.0293,
        "queries": qs_c,
        "DISCLOSED_WEAKNESS": "authored by an agent that had already read router.py and "
        "semantic.py; a blind set is the settling experiment",
    }
    flush()

    log("stage5: measure - lane set on the HELD-OUT index (the honest configuration)")
    REPORT["stages"]["stage5_lane_heldout"] = measure(
        router_selector(r_lane),
        lane_rows,
        fits=lambda q, k: r_lane.route(q, k=k).fits,
    )
    flush()

    log("stage5b: measure - lane set on the RAW index (quantifies the circularity)")
    REPORT["stages"]["stage5b_lane_raw_circular"] = measure(
        router_selector(r_raw),
        lane_rows,
        fits=lambda q, k: r_raw.route(q, k=k).fits,
    )
    flush()

    log("stage5c: per-tier on the held-out index")
    tiers: dict[str, Any] = {}
    for tier in sorted({r["tier"] for r in lane_rows}):
        rows = [r for r in lane_rows if r["tier"] == tier]
        tiers[tier] = measure(
            router_selector(r_lane), rows, fits=lambda q, k: r_lane.route(q, k=k).fits
        )
    REPORT["stages"]["stage5c_lane_per_tier"] = tiers
    flush()

    log("stage5d: measure QS-B (mechanical, held out)")
    REPORT["stages"]["stage5d_qs_b"] = measure(router_selector(r_b), qs_b)
    flush()

    log("stage5e: measure QS-C (authored, raw index - no holdout needed)")
    REPORT["stages"]["stage5e_qs_c"] = measure(
        router_selector(r_raw), qs_c, fits=lambda q, k: r_raw.route(q, k=k).fits
    )
    flush()

    log("stage6: BOTH-STATES controls")
    all_caps = list(r_lane.index.records)

    def flood_everything(_q: str, _k: int) -> list[Any]:
        return all_caps

    def blind_topk(_q: str, k: int) -> list[Any]:
        return all_caps[:k]

    by_id = r_lane.index.by_id()

    def oracle(q: str, k: int) -> list[Any]:
        row = next((r for r in lane_rows if r["text"] == q), None)
        gold = row["gold"] if row else []
        return [by_id[g] for g in gold[:k] if g in by_id]

    real = REPORT["stages"]["stage5_lane_heldout"]
    ctl: dict[str, Any] = {}
    for name, sel in (
        ("flood_everything", flood_everything),
        ("query_blind_topk", blind_topk),
        ("gold_oracle", oracle),
    ):
        ctl[name] = measure(sel, lane_rows)
    # shuffled-gold control: rotate every gold label onto the next query
    rot = lane_rows[1:] + lane_rows[:1]
    shuffled = [
        {**r, "gold": rot[i]["gold"], "qid": r["qid"] + "-SHUF"}
        for i, r in enumerate(lane_rows)
    ]
    ctl["shuffled_gold"] = measure(
        router_selector(r_lane), [r for r in shuffled if r["gold"]]
    )

    k = "5"
    real_rec = real["per_k"][k]["recall"]
    shuf_rec = ctl["shuffled_gold"]["per_k"][k]["recall"]
    real_bpc = real["per_k"][k]["BYTES_PER_CORRECT_SELECTION"]
    flood_bpc = ctl["flood_everything"]["per_k"][k]["BYTES_PER_CORRECT_SELECTION"]
    blind_rec = ctl["query_blind_topk"]["per_k"][k]["recall"]
    blind_bytes = ctl["query_blind_topk"]["per_k"][k]["mean_card_bytes_per_query_ALL"]
    real_bytes = real["per_k"][k]["mean_card_bytes_per_query_ALL"]
    oracle_bpc = ctl["gold_oracle"]["per_k"][k]["BYTES_PER_CORRECT_SELECTION"]

    REPORT["stages"]["stage6_controls"] = {
        "selectors": ctl,
        "verdicts_at_k5": {
            "shuffled_gold_collapses": {
                "real_recall": real_rec,
                "shuffled_recall": shuf_rec,
                "collapsed": bool(
                    shuf_rec is not None and real_rec and shuf_rec < real_rec * 0.5
                ),
                "meaning": "if recall survived relabelling, the metric is not reading the "
                "selection at all",
            },
            "flood_is_visibly_more_expensive": {
                "real_bytes_per_correct": real_bpc,
                "flood_bytes_per_correct": flood_bpc,
                "ratio": round(flood_bpc / real_bpc, 1)
                if (real_bpc and flood_bpc)
                else None,
                "flood_recall": ctl["flood_everything"]["per_k"][k]["recall"],
                "PROBE_FIRES_on_seeded_flood": bool(
                    flood_bpc and real_bpc and flood_bpc > real_bpc * 5
                ),
                "PROBE_SILENT_on_shipped_router": bool(
                    real_bpc and flood_bpc and real_bpc < flood_bpc / 5
                ),
            },
            "bytes_alone_cannot_certify": {
                "query_blind_recall": blind_rec,
                "query_blind_mean_bytes": blind_bytes,
                "real_mean_bytes": real_bytes,
                "note": "a router that ignores the query costs comparable bytes, so a low "
                "byte count is NOT evidence of good selection - the two tables must both "
                "be read",
            },
            "oracle_floor": {
                "oracle_bytes_per_correct": oracle_bpc,
                "real_bytes_per_correct": real_bpc,
                "real_over_oracle": round(real_bpc / oracle_bpc, 2)
                if (oracle_bpc and real_bpc)
                else None,
                "meaning": "the oracle is the theoretical minimum bytes per correct "
                "selection for this corpus; real/oracle is the router's context-efficiency "
                "penalty over a perfect selector",
            },
        },
    }
    flush()

    log("stage7: cross-check against the lane's own committed numbers")
    lane_json = json.loads(LANE_MEASUREMENTS.read_text(encoding="utf-8"))
    lane_cc = lane_json["context_cost"]["per_k"]
    rows = []
    for kk in KS:
        mine = REPORT["stages"]["stage5_lane_heldout"]["per_k"][str(kk)]
        theirs = lane_cc[str(kk)]
        rows.append(
            {
                "k": kk,
                "lane_mean_card_bytes": theirs["mean_card_bytes"],
                "my_mean_card_bytes": mine["mean_card_bytes_per_query_ALL"],
                "delta": round(
                    mine["mean_card_bytes_per_query_ALL"] - theirs["mean_card_bytes"], 2
                ),
                "lane_peak_card_bytes": theirs["peak_card_bytes"],
                "my_peak_card_bytes": mine["peak_card_bytes"],
                "lane_mean_selected": theirs["mean_selected"],
                "my_mean_items": mine["mean_items_returned"],
                "lane_card_saving_ratio": theirs["card_saving_ratio"],
                "my_card_saving_ratio": mine["card_saving_ratio_vs_full_description"],
            }
        )
    lane_q = lane_json["quality"]
    qual_rows = []
    for tier in ("L1", "L2", "L4"):
        if tier not in lane_q or tier not in REPORT["stages"]["stage5c_lane_per_tier"]:
            continue
        for kk in KS:
            m = REPORT["stages"]["stage5c_lane_per_tier"][tier]["per_k"][str(kk)]
            qual_rows.append(
                {
                    "tier": tier,
                    "k": kk,
                    "lane_precision": lane_q[tier]["precision_at"][str(kk)],
                    "my_precision": m["precision"],
                    "lane_recall": lane_q[tier]["recall_at"][str(kk)],
                    "my_recall": m["recall"],
                    "lane_gold_hit": lane_q[tier]["gold_hit_rate_at"][str(kk)],
                    "my_gold_hit": m["gold_hit_rate"],
                }
            )
    REPORT["stages"]["stage7_crosscheck"] = {
        "lane_artifact": str(LANE_MEASUREMENTS),
        "byte_table": rows,
        "quality_table": qual_rows,
        "lane_L3_abstain_rate": lane_q.get("L3", {}).get("abstain_rate"),
        "my_L3_abstain_rate": REPORT["stages"]["stage5c_lane_per_tier"]
        .get("L3", {})
        .get("negatives", {})
        .get("abstain_rate"),
        "byte_definition_crosscheck": {
            "decisions_where_my_count_equals_Decision.injected_bytes": BYTE_XCHECK[
                "agree"
            ],
            "disagreements": BYTE_XCHECK["disagree"][:10],
            "n_disagreements": len(BYTE_XCHECK["disagree"]),
        },
    }
    REPORT["status"] = "COMPLETE"
    REPORT["elapsed_sec"] = round(time.time() - t0, 1)
    flush()
    log(f"SUCCESS:wave4-routing-probe elapsed={REPORT['elapsed_sec']}s -> {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        REPORT["status"] = "CRASHED"
        REPORT["traceback"] = traceback.format_exc()[-4000:]
        flush()
        print("FAILED:wave4-routing-probe see WAVE4-ROUTING-PROBE.json", flush=True)
        raise
