#!/usr/bin/env python
"""Phase 8 MEASUREMENT - precision/recall, skill-use breadth, task success, ablation.

Spec: "measurement of skill-use breadth and task success" (`_USER-PROMPTS.md:10961`).

THREE THINGS THIS MODULE REFUSES TO DO
--------------------------------------
1. **It will not report a precision/recall number without also reporting the leakage
   meter.** `evaluate()` returns per-tier `lexical_overlap` computed on the index the
   router ACTUALLY SAW (post-holdout for L1). A score without it is uninterpretable.

2. **It will not report task success it did not observe.** Real task success requires
   knowing whether the agent invoked the injected capability and whether the task then
   succeeded -- an outcome this unit cannot generate by routing queries at a corpus. So
   `task_success()` returns `NOT-CHECKED` with the reason when the outcome log is empty,
   and never a `0.0` that reads like a measurement. The plumbing to populate it is
   `record_outcome()`, and the live data source that already collects the equivalent
   signal is `hooks/semantic-router/success.py` (suggested-vs-acted counters).

3. **It will not claim its own detector works.** `controls()` runs two BOTH-STATES
   probes before any headline number is trusted:
     * SHUFFLED GOLD -- relabel every query with a wrong gold id. Recall MUST collapse.
       If it does not, the metric is not measuring selection at all.
     * FLOOD ROUTER -- a router that returns the top-k by nothing but corpus order,
       and one that returns EVERYTHING. Recall may rise; injected bytes must explode.
       This is the control that gives the anti-flooding claim its meaning: without it,
       "we get good recall at low bytes" has no counterfactual.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import budget
from . import queries as qmod
from .index import Capability, Index, discover
from .router import Router

#: Append-only outcome log. JSONL so a crashed session leaves valid prior lines.
OUTCOME_LOG = Path(
    os.environ.get("ROUTING_OUTCOME_LOG")
    or (Path(__file__).resolve().parent / "outcomes.jsonl")
)

#: k values reported for precision/recall. Mirrors budget.K_LADDER so the quality and
#: cost tables line up row-for-row -- reading them at different k is how a flood hides.
K_LADDER = budget.K_LADDER


# --------------------------------------------------------------------------- core


def _prf(selected: list[str], gold: frozenset[str]) -> tuple[float, float]:
    """(precision, recall) for one decision, STRICT exact-id matching.

    NEGATIVE queries (`gold` empty) are scored separately by `evaluate` -- precision on
    an empty gold set is undefined, and returning 0.0 would silently punish a router
    for correctly staying silent. Guarding it here would hide that asymmetry; it is
    handled explicitly at the call site instead.
    """
    if not gold:  # pragma: no cover - callers must not route negatives here
        raise ValueError("negative queries are scored by evaluate(), not _prf")
    hit = len([s for s in selected if s in gold])
    precision = hit / len(selected) if selected else 0.0
    recall = hit / len(gold)
    return precision, recall


def expand_gold(gold: frozenset[str], idx: Index) -> frozenset[str]:
    """Widen a gold set to include CONTENT-VERIFIED mirror duplicates of its members.

    Justification, and the reason this is reported SEPARATELY rather than folded into the
    headline: when the harness mirrors `~/.claude/commands/aside.md` into
    `~/.agents/skills/source-command-aside/`, selecting the mirror is substantively the
    right answer -- same capability, same content (measured token-Jaccard 1.000 for that
    pair). Charging it as a miss measures the inventory's duplication, not the router.

    But loosening a metric in one's own favour is exactly how a score stops meaning
    anything, so `evaluate()` reports STRICT and MIRROR-CREDITED side by side and the
    strict figure remains the headline. Only mirror equivalence widens the set; the 18
    cross-class same-name records (`mcp:figma` vs `skill:figma`) are NOT interchangeable
    and are never credited.
    """
    groups = idx.equivalence_groups()
    out = set(gold)
    by_id = idx.by_id()
    for gid in gold:
        rec = by_id.get(gid)
        if rec is not None and rec.equiv_key:
            out.update(groups.get(rec.equiv_key, []))
    return frozenset(out)


@dataclass
class TierResult:
    tier: str
    n: int
    precision_at: dict[int, float] = field(default_factory=dict)
    recall_at: dict[int, float] = field(default_factory=dict)
    hit_rate_at: dict[int, float] = field(default_factory=dict)
    mirror_hit_rate_at: dict[int, float] = field(default_factory=dict)
    mean_lexical_overlap: float = 0.0
    max_lexical_overlap: float = 0.0
    failures: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "tier": self.tier,
            "n": self.n,
            "precision_at": {
                str(k): round(v, 4) for k, v in sorted(self.precision_at.items())
            },
            "recall_at": {
                str(k): round(v, 4) for k, v in sorted(self.recall_at.items())
            },
            "gold_hit_rate_at": {
                str(k): round(v, 4) for k, v in sorted(self.hit_rate_at.items())
            },
            "gold_hit_rate_mirror_credited_at": {
                str(k): round(v, 4) for k, v in sorted(self.mirror_hit_rate_at.items())
            },
            "mean_lexical_overlap_post_holdout": round(self.mean_lexical_overlap, 4),
            "max_lexical_overlap_post_holdout": round(self.max_lexical_overlap, 4),
            "failures": self.failures[:10],
        }


@dataclass
class NegativeResult:
    """Scoring for the L3 no-fit tier. `abstain_rate` is the metric that matters."""

    n: int
    abstained: int
    fired: list[dict] = field(default_factory=list)

    @property
    def abstain_rate(self) -> float:
        return self.abstained / self.n if self.n else 0.0

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "abstained": self.abstained,
            "abstain_rate": round(self.abstain_rate, 4),
            "false_fires": self.fired[:10],
        }


def evaluate(
    router: Router,
    qset: qmod.QuerySet,
    *,
    eval_index: Index | None = None,
    ks: tuple[int, ...] = K_LADDER,
) -> dict:
    """Precision/recall per tier, plus the negative tier and the leakage meter.

    `eval_index` is the index the router was BUILT from; it is used only to compute the
    leakage meter against the text the router could actually see. Passing the pre-holdout
    index here would report an overlap number that no longer describes the experiment.
    """
    idx_for_overlap = eval_index if eval_index is not None else router.index
    out: dict = {}

    for tier in ("L1", "L2", "L4"):
        qs = qset.by_tier(tier)
        if not qs:
            continue
        res = TierResult(tier=tier, n=len(qs))
        ov = [qmod.lexical_overlap(q.text, idx_for_overlap, q.gold) for q in qs]
        res.mean_lexical_overlap = sum(ov) / len(ov) if ov else 0.0
        res.max_lexical_overlap = max(ov) if ov else 0.0
        for k in ks:
            ps, rs, hs, ms = [], [], [], []
            for q in qs:
                sel = router.route(q.text, k=k).ids
                p, r = _prf(sel, q.gold)
                wide = expand_gold(q.gold, idx_for_overlap)
                mr = _prf(sel, wide)[1]
                ps.append(p)
                rs.append(r)
                hs.append(1.0 if r > 0 else 0.0)
                ms.append(1.0 if mr > 0 else 0.0)
                if k == max(ks) and mr <= 0:
                    res.failures.append(
                        {
                            "qid": q.qid,
                            "query": q.text[:90],
                            "gold": sorted(q.gold),
                            "got": sel[:5],
                        }
                    )
            res.precision_at[k] = sum(ps) / len(ps)
            res.recall_at[k] = sum(rs) / len(rs)
            res.hit_rate_at[k] = sum(hs) / len(hs)
            res.mirror_hit_rate_at[k] = sum(ms) / len(ms)
        out[tier] = res.as_dict()

    negs = qset.by_tier("L3")
    if negs:
        nr = NegativeResult(n=len(negs), abstained=0)
        for q in negs:
            d = router.route(q.text, k=max(ks))
            if not d.fits:
                nr.abstained += 1
            else:
                nr.fired.append(
                    {
                        "qid": q.qid,
                        "query": q.text[:90],
                        "got": d.ids[:3],
                        "confidence": round(d.confidence, 3),
                    }
                )
        out["L3"] = nr.as_dict()

    # L1 sub-tiers reported separately: L1a is paraphrase-shaped (a declared trigger),
    # L1b is documentation-shaped (a declared description sentence). Averaging them
    # would let easy retrieval mask weak paraphrase handling.
    for sub in ("L1a", "L1b"):
        qs = [q for q in qset.by_tier("L1") if q.qid.startswith(sub)]
        if not qs:
            continue
        sr = TierResult(tier=sub, n=len(qs))
        for k in ks:
            rs = [_prf(router.route(q.text, k=k).ids, q.gold)[1] for q in qs]
            sr.recall_at[k] = sum(rs) / len(rs)
            sr.hit_rate_at[k] = sum(1.0 for r in rs if r > 0) / len(rs)
        out[sub] = {
            "tier": sub,
            "n": sr.n,
            "recall_at": {str(k): round(v, 4) for k, v in sorted(sr.recall_at.items())},
            "gold_hit_rate_at": {
                str(k): round(v, 4) for k, v in sorted(sr.hit_rate_at.items())
            },
        }
    return out


# --------------------------------------------------------------------------- breadth


@dataclass
class BreadthResult:
    """Skill-use BREADTH. The spec's opening constraint made measurable.

    "Do not prune capabilities merely because they were rarely used" is only meaningful
    if the tail is actually REACHABLE. So breadth is measured two ways:
      * `distinct_selected` / `classes_selected` -- how much of the repertoire the router
        ever reaches over a query stream (a router collapsed onto ten favourites is the
        failure mode this detects);
      * `tail_reachable` -- of a sample of capabilities, how many can be selected by a
        query derived from their OWN text. A capability that cannot win even then is
        effectively pruned, whatever the docs say.
    """

    n_queries: int
    distinct_selected: int
    corpus_size: int
    classes_selected: dict[str, int] = field(default_factory=dict)
    class_coverage: dict[str, str] = field(default_factory=dict)
    tail_sampled: int = 0
    tail_reachable: int = 0
    unreachable_examples: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "n_queries": self.n_queries,
            "distinct_capabilities_selected": self.distinct_selected,
            "corpus_size": self.corpus_size,
            "selected_by_class": dict(sorted(self.classes_selected.items())),
            "class_coverage": dict(sorted(self.class_coverage.items())),
            "tail_sampled": self.tail_sampled,
            "tail_reachable": self.tail_reachable,
            "tail_reachable_rate": (
                round(self.tail_reachable / self.tail_sampled, 4)
                if self.tail_sampled
                else None
            ),
            "unreachable_examples": self.unreachable_examples[:10],
        }


def breadth(
    router: Router, qset: qmod.QuerySet, *, k: int = 5, tail_stride: int = 17
) -> BreadthResult:
    """Measure repertoire reach over the query stream, then probe the tail directly.

    `tail_stride` walks the corpus at a fixed stride rather than sampling randomly, so
    the probe is deterministic and its coverage is stated rather than lucky.
    """
    seen: set[str] = set()
    per_cls: dict[str, int] = {}
    for q in qset.queries:
        for cid in router.route(q.text, k=k).ids:
            seen.add(cid)
    for cid in seen:
        cls = cid.split(":", 1)[0]
        per_cls[cls] = per_cls.get(cls, 0) + 1

    res = BreadthResult(
        n_queries=len(qset.queries),
        distinct_selected=len(seen),
        corpus_size=len(router.index),
        classes_selected=per_cls,
    )
    total_by_cls: dict[str, int] = dict(router.index.counts)
    for cls, tot in sorted(total_by_cls.items()):
        res.class_coverage[cls] = f"{per_cls.get(cls, 0)}/{tot}"

    # Tail reachability: derive a query from each sampled capability's own text and ask
    # whether it can be selected at all. This is the "rarely used != prunable" check.
    for i in range(0, len(router.index.records), tail_stride):
        rec = router.index.records[i]
        probe = (rec.desc_source or rec.name)[:180]
        if len(probe) < 12:
            continue
        res.tail_sampled += 1
        if rec.id in router.route(probe, k=k).ids:
            res.tail_reachable += 1
        else:
            res.unreachable_examples.append(rec.id)
    return res


# ----------------------------------------------------------------------- task success


def record_outcome(
    query: str,
    selected: list[str],
    invoked: str | None,
    succeeded: bool | None,
    *,
    path: Path | None = None,
) -> None:
    """Append one routing OUTCOME. The only legitimate source of task-success data."""
    p = path or OUTCOME_LOG
    rec = {
        "query": query[:300],
        "selected": selected[:10],
        "invoked": invoked,
        "succeeded": succeeded,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def task_success(path: Path | None = None) -> dict:
    """Task-success statistics from recorded outcomes.

    Returns `verdict: NOT-CHECKED` when no outcomes exist. It does NOT return zeros:
    an unpopulated log and a router that never helps are different findings, and
    collapsing them is how a measurement becomes a lie.
    """
    p = path or OUTCOME_LOG
    if not p.exists():
        return {
            "verdict": "NOT-CHECKED",
            "reason": f"no outcome log at {p}; task success requires live invoke/outcome "
            "signal, which routing a query corpus cannot produce",
            "how_to_populate": "call record_outcome() from the live routing path; the "
            "equivalent live collector already exists at hooks/semantic-router/success.py",
            "n": 0,
        }
    rows = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if not rows:
        return {"verdict": "NOT-CHECKED", "reason": f"outcome log {p} is empty", "n": 0}
    graded = [r for r in rows if isinstance(r.get("succeeded"), bool)]
    invoked = [r for r in rows if r.get("invoked")]
    per_cap: dict[str, dict[str, int]] = {}
    for r in graded:
        cid = r.get("invoked") or "(none)"
        d = per_cap.setdefault(cid, {"n": 0, "ok": 0})
        d["n"] += 1
        d["ok"] += 1 if r["succeeded"] else 0
    return {
        "verdict": "MEASURED",
        "n": len(rows),
        "graded": len(graded),
        "invoke_rate": round(len(invoked) / len(rows), 4),
        "success_rate": round(sum(1 for r in graded if r["succeeded"]) / len(graded), 4)
        if graded
        else None,
        "per_capability": {
            k: {"n": v["n"], "success_rate": round(v["ok"] / v["n"], 4)}
            for k, v in sorted(per_cap.items())
        },
    }


# --------------------------------------------------------------------------- ablation

#: name -> Router.build kwargs. Each isolates one component's contribution.
ABLATIONS: dict[str, dict] = {
    "full": {},
    # Expansion defaults OFF on a measured negative result, so the ablation arm turns it
    # ON. The arm name states the direction so the delta cannot be misread as a removal.
    "with_concept_expansion": {"use_expansion": True},
    "no_char_ngram": {"use_ngram": False},
    "no_structural_enrichment": {"enrich": False},
}


def ablate(idx: Index, qset: qmod.QuerySet, *, k: int = 5) -> dict:
    """Recall@k and mean injected bytes for each ablation, on ONE shared index copy.

    Every variant is fitted from a deep copy so an enrichment applied by one variant
    cannot leak into the next -- `descriptions.enrich` mutates `routing_text` in place,
    and sharing the index between variants would make the ablation measure nothing.
    """
    import copy as _copy

    out: dict = {}
    scored = [q for q in qset.queries if q.gold]
    for name, kwargs in ABLATIONS.items():
        r = Router.build(_copy.deepcopy(idx), **kwargs)
        rec, byts = [], []
        for q in scored:
            d = r.route(q.text, k=k)
            _p, rr = _prf(d.ids, q.gold)
            rec.append(rr)
            byts.append(d.injected_bytes)
        negs = qmod_negatives(r, qset)
        out[name] = {
            "recall_at_k": round(sum(rec) / len(rec), 4) if rec else None,
            "gold_hit_rate": round(sum(1 for x in rec if x > 0) / len(rec), 4)
            if rec
            else None,
            "mean_injected_bytes": round(sum(byts) / len(byts), 1) if byts else None,
            "negative_abstain_rate": negs,
        }
    base = out.get("full", {}).get("recall_at_k")
    if base is not None:
        for name, d in out.items():
            if d["recall_at_k"] is not None:
                d["delta_vs_full"] = round(d["recall_at_k"] - base, 4)
    return out


def qmod_negatives(router: Router, qset: qmod.QuerySet, k: int = 5) -> float | None:
    negs = qset.by_tier("L3")
    if not negs:
        return None
    return round(
        sum(1 for q in negs if not router.route(q.text, k=k).fits) / len(negs), 4
    )


# --------------------------------------------------------------------------- controls


def flood_selector(idx: Index, mode: str) -> Callable[[str, int], list[Capability]]:
    """Deliberately-bad selectors, for the both-states control.

    `topk_ignoring_query` -- returns the first k records regardless of the query.
    `everything`          -- returns the entire corpus. The literal "achieve recall by
                             injecting everything" router the spec says has failed.
    """
    if mode == "everything":
        return lambda _q, _k: list(idx.records)
    return lambda _q, k: list(idx.records[:k])


def controls(router: Router, qset: qmod.QuerySet, *, k: int = 5) -> dict:
    """BOTH-STATES probes. Every headline number below is meaningless without these.

    A metric that cannot be made to fail is not measuring anything.
    """
    scored = [q for q in qset.queries if q.gold]

    # (1) SHUFFLED GOLD. Rotate every gold label onto the NEXT query. Recall must
    # collapse. If it stays high, `_prf` is not reading the selection.
    rot = [q.gold for q in scored[1:]] + [scored[0].gold] if scored else []
    shuffled = []
    for q, wrong in zip(scored, rot):
        sel = router.route(q.text, k=k).ids
        shuffled.append(_prf(sel, wrong)[1])
    real = [_prf(router.route(q.text, k=k).ids, q.gold)[1] for q in scored]
    real_recall = sum(real) / len(real) if real else 0.0
    shuf_recall = sum(shuffled) / len(shuffled) if shuffled else 0.0

    # (2) FLOOD ROUTERS. Priced with the same accounting as the real router.
    texts = [q.text for q in qset.queries]
    real_rep = budget.measure(
        texts, lambda q, kk: [c for c, _s in router.route(q, k=kk).selected], ks=(k,)
    )
    flood_rep = budget.measure(
        texts, flood_selector(router.index, "everything"), ks=(k,)
    )
    blind_rep = budget.measure(
        texts, flood_selector(router.index, "topk_ignoring_query"), ks=(k,)
    )

    flood_recall = []
    for q in scored:
        flood_recall.append(_prf([c.id for c in router.index.records], q.gold)[1])

    real_bytes = real_rep.per_k[k]["mean_card_bytes"]
    flood_bytes = flood_rep.per_k[k]["mean_card_bytes"]

    return {
        "shuffled_gold_control": {
            "real_recall": round(real_recall, 4),
            "shuffled_recall": round(shuf_recall, 4),
            "collapsed": shuf_recall < real_recall * 0.5,
            "verdict": (
                "DETECTOR VALID - recall collapses on wrong labels"
                if shuf_recall < real_recall * 0.5
                else "DETECTOR INVALID - recall survived relabelling; the metric is not "
                "reading the selection"
            ),
        },
        "flood_control": {
            "everything_router_recall": round(sum(flood_recall) / len(flood_recall), 4)
            if flood_recall
            else None,
            "everything_router_mean_bytes": round(flood_bytes, 1),
            "real_router_recall": round(real_recall, 4),
            "real_router_mean_bytes": round(real_bytes, 1),
            "byte_ratio_flood_over_real": round(flood_bytes / real_bytes, 1)
            if real_bytes
            else None,
            "verdict": (
                "ANTI-FLOOD METRIC VALID - the perfect-recall router costs "
                f"{flood_bytes / real_bytes:.0f}x the bytes"
                if real_bytes and flood_bytes > real_bytes * 5
                else "ANTI-FLOOD METRIC INVALID - flooding is not visibly more expensive"
            ),
        },
        "query_blind_control": {
            "blind_topk_mean_bytes": round(blind_rep.per_k[k]["mean_card_bytes"], 1),
            "note": "a query-blind router costs comparable BYTES to the real one, which is "
            "why bytes alone can never certify a router - the quality table and the cost "
            "table must both be read",
        },
    }


# --------------------------------------------------------------------------- driver


def full_report(*, k_ladder: tuple[int, ...] = K_LADDER) -> dict:
    """Everything, in one deterministic pass. This is what the gate and the doc quote."""
    import copy as _copy

    raw = discover()
    qset = qmod.build(raw)
    # The router MUST be built from the held-out index, or L1 is circular.
    held = qmod.holdout_index(raw, qset.queries)
    router = Router.build(_copy.deepcopy(held))

    ev = evaluate(router, qset, eval_index=router.index, ks=k_ladder)
    br = breadth(router, qset)
    rep = budget.measure(
        [q.text for q in qset.queries],
        lambda q, kk: [c for c, _s in router.route(q, k=kk).selected],
        ks=k_ladder,
    )
    ok, msg = budget.verify(rep)
    return {
        "index": {
            "total": len(raw),
            "counts": dict(sorted(raw.counts.items())),
            "floor_violations": raw.verify_floors(),
        },
        "query_set": {
            "counts": qset.counts(),
            "total": len(qset.queries),
            "unresolved_gold": qset.unresolved_gold,
        },
        "quality": ev,
        "breadth": br.as_dict(),
        "context_cost": rep.as_dict(),
        "context_cost_verdict": msg,
        "always_loaded_baseline": budget.always_loaded_baseline(raw),
        "task_success": task_success(),
        "controls": controls(router, qset),
        "ablation": ablate(_copy.deepcopy(held), qset),
        "budget_ok": ok,
    }


def main(argv: list[str] | None = None) -> int:
    """Full report. `--out PATH` writes PURE JSON to PATH.

    MEASURED DEFECT this closes: the committed `MEASUREMENTS.json` was produced by
    redirecting stdout, so the terminal `SUCCESS:routing-metrics` marker landed after the
    closing brace and the file failed `json.loads` with
    `JSONDecodeError: Extra data: line 529`. A `.json` artifact that no consumer can parse
    is broken regardless of how correct its contents are -- and every reader of it in this
    unit had been hand-trimming the last line, which is how the breakage stayed invisible.
    `--out` keeps the marker on stdout (AGENTS.md 4) and the artifact machine-readable.
    Asserted by `test_regression_no_flood.py::test_the_committed_measurements_file_parses`.
    """
    import sys

    argv = list(sys.argv[1:] if argv is None else argv)
    out_path: Path | None = None
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 >= len(argv):
            print("FAILED:routing-metrics --out requires a path")
            return 1
        out_path = Path(argv[i + 1])

    rep = full_report()
    blob = json.dumps(rep, indent=2) + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" so Python does not translate to CRLF on Windows: the committed bytes
        # must equal the bytes CI checks out (windows-shell.md 8b).
        with open(out_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(blob)
        print(f"wrote {out_path} ({len(blob.encode('utf-8'))} bytes)")
    else:
        print(blob, end="")

    bad: list[str] = []
    if rep["index"]["floor_violations"]:
        bad.append("index-floor")
    if rep["query_set"]["unresolved_gold"]:
        bad.append("unresolved-gold")
    if not rep["budget_ok"]:
        bad.append("budget")
    if not rep["controls"]["shuffled_gold_control"]["collapsed"]:
        bad.append("detector-invalid")
    if "INVALID" in rep["controls"]["flood_control"]["verdict"]:
        bad.append("antiflood-metric-invalid")
    if bad:
        print(f"FAILED:routing-metrics {','.join(bad)}")
        return 1
    print(f"SUCCESS:routing-metrics queries={rep['query_set']['total']}")
    return 0
