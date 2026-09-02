"""THE regression suite the spec's final clause demands.

  "a regression suite proving the router selects relevant capabilities without flooding
   context"  --  `_USER-PROMPTS.md:10962`

Two properties must hold SIMULTANEOUSLY, and the whole point of this file is that neither
can be bought with the other:

  A. SELECTION QUALITY  -- the right capability is surfaced, on a labelled set with a
     disclosed labelling protocol, with the L1 tier held out so it is not circular.
  B. CONTEXT COST       -- injected bytes stay bounded, measured at k = 1, 3, 5, 10.

A suite that asserted only (A) would pass for a router that injects the whole 912-record
catalogue. A suite that asserted only (B) would pass for a router that injects nothing, or
for one that ignores the query entirely. So each property is pinned against a
DELIBERATELY-BAD counterfactual:

  * the EVERYTHING router      -- perfect recall, measured 298x the bytes  -> fails (B)
  * the QUERY-BLIND top-k      -- comparable bytes, no relevance           -> fails (A)
  * SHUFFLED GOLD LABELS       -- proves the quality metric reads selection at all

Every threshold asserted below is a REGRESSION BAR pinned to a measured value, deliberately
set with headroom so ordinary drift does not turn the gate into noise, but tight enough
that a real collapse trips it. The measured values at the time of writing are quoted inline
next to each bar; a bar with no measured value beside it would be a guess.
"""

from __future__ import annotations

import copy

import pytest
from routing import budget, metrics
from routing import queries as qmod
from routing.index import CARD_BYTE_CAP, discover
from routing.router import Router

# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def raw():
    return discover()


@pytest.fixture(scope="module")
def qset(raw):
    return qmod.build(raw)


@pytest.fixture(scope="module")
def held_router(raw, qset):
    """The router under test is built from the HELD-OUT index.

    This is what keeps tier L1 honest: each L1 query's source sentence is removed from its
    own record before the router ever sees it. Building from the raw index instead would
    make L1 a string-equality check that scores ~1.0 and proves nothing.
    """
    return Router.build(copy.deepcopy(qmod.holdout_index(raw, qset.queries)))


@pytest.fixture(scope="module")
def selector(held_router):
    return lambda q, k: [c for c, _s in held_router.route(q, k=k).selected]


# The four expensive computations are MODULE-scoped so the suite pays for each exactly
# once. Before this, every assertion re-ran the full evaluation and the file took 11m22s;
# a regression gate nobody is willing to run is not a gate.
@pytest.fixture(scope="module")
def ev(held_router, qset):
    return metrics.evaluate(held_router, qset, eval_index=held_router.index)


@pytest.fixture(scope="module")
def rep(qset, selector):
    return budget.measure([q.text for q in qset.queries], selector)


@pytest.fixture(scope="module")
def ctrls(held_router, qset):
    return metrics.controls(held_router, qset)


@pytest.fixture(scope="module")
def br(held_router, qset):
    return metrics.breadth(held_router, qset)


# ======================================================================= B. CONTEXT COST


def test_injected_bytes_are_bounded_at_every_k_in_the_ladder(qset, rep):
    """Measured (mean card bytes / peak):
    k=1 161.9/219 . k=3 389.6/657 . k=5 494.4/1043 . k=10 530.2/1322."""
    ok, msg = budget.verify(rep)
    assert ok, msg
    assert rep.checked == len(qset.queries) * len(budget.K_LADDER)
    for k in budget.K_LADDER:
        peak = rep.per_k[k]["peak_card_bytes"]
        assert peak <= k * CARD_BYTE_CAP, (k, peak)
        assert rep.per_k[k]["mean_card_bytes"] <= 1200, (k, rep.per_k[k])


def test_bytes_grow_sublinearly_in_k(rep):
    """k=10 must NOT cost ten times k=1. If it does, the router is padding to fill k
    rather than selecting what is relevant -- flooding with extra steps."""
    b1 = rep.per_k[1]["mean_card_bytes"]
    b10 = rep.per_k[10]["mean_card_bytes"]
    assert b10 < b1 * 5, (b1, b10)
    assert rep.per_k[10]["mean_selected"] < 10 * 0.6, rep.per_k[10]["mean_selected"]


def test_the_card_projection_is_what_makes_this_cheap(rep):
    """Measured saving ratio 7.8-8.5x vs injecting the routing text of the SAME picks.
    The bar is 3x: this asserts the mechanism, not a fitted number."""
    for k in budget.K_LADDER:
        assert rep.per_k[k]["card_saving_ratio"] >= 3.0, (k, rep.per_k[k])


def test_verify_fails_closed_on_an_empty_measurement():
    """A harness that priced zero selections must not report success. 'Nothing exceeded
    the cap' is exactly what a broken measurement also reports."""
    ok, msg = budget.verify(budget.BudgetReport(n_queries=0))
    assert ok is False and "no-selections-priced" in msg


def test_verify_fails_on_a_real_cap_breach(qset):
    """BOTH-STATES for the byte gate: it must go RED for an over-cap selector."""
    idx = discover()
    rep = budget.measure(
        [q.text for q in qset.queries][:5],
        metrics.flood_selector(idx, "everything"),
        ks=(5,),
    )
    ok, msg = budget.verify(rep)
    assert ok is False and "over-cap" in msg, msg


def test_an_abstention_costs_exactly_zero_bytes(held_router):
    d = held_router.route(
        "what is the capital of Mongolia and how many people live there", k=10
    )
    assert d.fits is False
    assert d.injected_bytes == 0


# =================================================================== A. SELECTION QUALITY


def test_the_committed_measurements_file_parses_as_json():
    """MEASURED DEFECT: `MEASUREMENTS.json` was generated by shell redirect, so the
    terminal SUCCESS marker landed after the closing brace and the file failed
    `json.loads` with `Extra data: line 529`. Regenerate it with
    `cli.py metrics --out platform/routing/MEASUREMENTS.json`, never `> file`.

    Also asserts the file is LF-only: a CRLF artifact differs from the bytes CI checks out.
    """
    import json as _json
    from pathlib import Path as _P

    p = _P(__file__).resolve().parent / "MEASUREMENTS.json"
    assert p.is_file(), p
    raw = p.read_bytes()
    assert b"\r\n" not in raw, (
        "MEASUREMENTS.json has CRLF; the tree must match the CI blob"
    )
    doc = _json.loads(raw.decode("utf-8"))
    for key in (
        "index",
        "query_set",
        "quality",
        "breadth",
        "context_cost",
        "controls",
        "ablation",
    ):
        assert key in doc, key
    assert doc["index"]["total"] > 800
    assert doc["task_success"]["verdict"] in ("NOT-CHECKED", "MEASURED")


def test_the_labelled_set_is_well_formed(qset):
    assert qset.unresolved_gold == [], qset.unresolved_gold
    c = qset.counts()
    assert c.get("L1", 0) >= 20 and c.get("L2", 0) >= 15
    assert c.get("L3", 0) >= 5, "negatives are required or abstention is never tested"
    assert c.get("L4", 0) >= 4, (
        "multi-label queries are required or recall@k is untested"
    )
    assert len(qset.queries) >= 50, len(qset.queries)


def test_held_out_tier_recall_meets_its_bar(ev):
    """L1 measured gold-hit@5 = 0.750 strict / 0.7857 mirror-credited. Bar 0.60."""
    hit5 = ev["L1"]["gold_hit_rate_at"]["5"]
    assert hit5 >= 0.60, f"L1 gold-hit@5 regressed to {hit5}"


def test_the_holdout_is_real_not_decorative(raw, qset):
    """The withheld sentence must actually be ABSENT from the record the router sees.
    Without this, L1 is circular and its recall number is meaningless."""
    held = qmod.holdout_index(raw, qset.queries)
    by_id = held.by_id()
    checked = 0
    for q in qset.by_tier("L1"):
        rec = by_id[q.holdout_id]
        assert q.holdout_text not in rec.routing_text, q.qid
        assert q.holdout_text not in rec.triggers, q.qid
        checked += 1
    assert checked >= 20, f"only {checked} holdouts verified"


def test_holdout_does_not_mutate_the_source_index(raw, qset):
    """D3's lesson: a test that mutates what it measures. `holdout_index` must COPY."""
    before = {r.id: r.routing_text for r in raw.records}
    qmod.holdout_index(raw, qset.queries)
    after = {r.id: r.routing_text for r in raw.records}
    assert before == after, "holdout_index mutated the shared index"


def test_paraphrase_tier_is_not_a_keyword_giveaway(ev):
    """The leakage meter. L2 mean lexical overlap with the gold description measured
    0.0293 -- these are genuine paraphrases, not restatements."""
    assert ev["L2"]["mean_lexical_overlap_post_holdout"] < 0.20, ev["L2"]
    assert ev["L2"]["max_lexical_overlap_post_holdout"] < 0.40, ev["L2"]


def test_multi_label_queries_surface_at_least_one_relevant_capability(ev):
    """L4 measured gold-hit@5 = 0.60. Bar 0.40."""
    assert ev["L4"]["gold_hit_rate_at"]["5"] >= 0.40, ev["L4"]


def test_the_router_abstains_on_most_no_fit_queries(ev):
    """L3 measured abstain 0.667 (4/6). Bar 0.50.

    The two remaining fires are disclosed rather than relabelled: L3-04 ("translate this
    sentence into French") routes to `skill:subtitle-translate`, which is arguably a
    DEFENSIBLE route and therefore a labelling disagreement as much as a router error;
    L3-05 ("what did I have for lunch yesterday") -> `skill:cost-tracking` is a genuine
    false fire. Relabelling L3-04 to make the number look better would be tuning the test
    set, so the label stands and the disagreement is stated here.
    """
    assert ev["L3"]["abstain_rate"] >= 0.50, ev["L3"]


# ============================================================ COUNTERFACTUALS (both-states)


def test_shuffled_gold_labels_collapse_the_quality_metric(ctrls):
    """If recall survived relabelling, the metric would not be reading the selection.
    Measured: real 0.5463 -> shuffled 0.000."""
    c = ctrls["shuffled_gold_control"]
    assert c["collapsed"] is True, c
    assert c["shuffled_recall"] < c["real_recall"] * 0.5, c
    assert "DETECTOR VALID" in c["verdict"]


def test_the_everything_router_wins_recall_and_loses_on_bytes(ctrls):
    """The literal counterfactual the spec names. Measured: recall 1.0 at 298x the bytes.

    This is the assertion that gives 'without flooding context' operational meaning."""
    c = ctrls["flood_control"]
    assert c["everything_router_recall"] == 1.0, c
    assert c["byte_ratio_flood_over_real"] >= 50, c
    assert "ANTI-FLOOD METRIC VALID" in c["verdict"]


def test_a_query_blind_router_is_cheap_but_irrelevant(held_router, qset, raw):
    """Bytes ALONE can never certify a router. A selector that ignores the query entirely
    costs comparable bytes (measured 1,076 B) while being useless -- so the byte table must
    always be read next to the quality table, never instead of it."""
    blind = metrics.flood_selector(raw, "topk_ignoring_query")
    rep = budget.measure([q.text for q in qset.queries], blind, ks=(5,))
    assert budget.verify(rep)[0] is True, "the blind selector is within the byte cap..."
    scored = [q for q in qset.queries if q.gold]
    hits = sum(1 for q in scored if any(c.id in q.gold for c in blind(q.text, 5)))
    assert hits / len(scored) < 0.10, "...yet must be near-useless on relevance"


def test_quality_and_cost_bars_are_not_satisfiable_by_the_same_degenerate_router(
    held_router, qset, raw
):
    """The suite's own integrity check: no single degenerate strategy passes BOTH families
    of assertions above. Asserted directly rather than left as a design comment."""
    scored = [q for q in qset.queries if q.gold]

    everything = metrics.flood_selector(raw, "everything")
    ev_rep = budget.measure([q.text for q in qset.queries], everything, ks=(5,))
    assert budget.verify(ev_rep)[0] is False, (
        "everything-router must FAIL the byte family"
    )

    def nothing(_q, _k):
        return []

    n_rep = budget.measure([q.text for q in qset.queries], nothing, ks=(5,))
    assert budget.verify(n_rep)[0] is True, "empty-router passes bytes..."
    n_hits = sum(1 for q in scored if any(c.id in q.gold for c in nothing(q.text, 5)))
    assert n_hits == 0, "...and scores zero on quality"

    real_rep = budget.measure(
        [q.text for q in qset.queries],
        lambda q, k: [c for c, _s in held_router.route(q, k=k).selected],
        ks=(5,),
    )
    assert budget.verify(real_rep)[0] is True
    real_hits = sum(
        1
        for q in scored
        if any(i in q.gold for i in held_router.route(q.text, k=5).ids)
    )
    assert real_hits / len(scored) >= 0.40, real_hits / len(scored)


# ================================================================= BREADTH (no pruning)


def test_the_tail_of_the_repertoire_is_reachable(br):
    """The spec's opening constraint, made falsifiable: "Do not prune capabilities merely
    because they were rarely used." A capability that cannot be selected even by a query
    derived from its OWN description is effectively pruned, whatever the docs say.

    Measured tail_reachable_rate = 0.9815 (53/54 sampled). Bar 0.85."""
    assert br.tail_sampled >= 40, br.tail_sampled
    rate = br.tail_reachable / br.tail_sampled
    assert rate >= 0.85, (
        f"{br.tail_reachable}/{br.tail_sampled} reachable: {br.unreachable_examples}"
    )


def test_selection_spans_the_capability_classes(br):
    """A router that only ever reaches skills has silently pruned the platform inventory
    -- 102 blueprints, 48 protocols, 69 presets, 164 candidates."""
    assert br.distinct_selected >= 80, br.distinct_selected
    reached = {c for c, n in br.classes_selected.items() if n > 0}
    for required in ("skill", "workflow", "protocol", "preset", "candidate"):
        assert required in reached, (
            f"class {required} never selected: {br.classes_selected}"
        )


# ================================================================= TASK SUCCESS honesty


def test_task_success_reports_NOT_CHECKED_rather_than_a_fabricated_zero(tmp_path):
    """An unpopulated outcome log and a router that never helps are different findings."""
    out = metrics.task_success(tmp_path / "absent.jsonl")
    assert out["verdict"] == "NOT-CHECKED"
    assert out["n"] == 0
    assert "reason" in out and "how_to_populate" in out


def test_task_success_becomes_MEASURED_once_outcomes_exist(tmp_path):
    """BOTH-STATES for the honesty guard: it must switch to a real measurement when
    real data arrives, or the NOT-CHECKED branch is unfalsifiable."""
    log = tmp_path / "outcomes.jsonl"
    metrics.record_outcome("q1", ["skill:reframe"], "skill:reframe", True, path=log)
    metrics.record_outcome("q2", ["skill:reframe"], "skill:reframe", False, path=log)
    out = metrics.task_success(log)
    assert out["verdict"] == "MEASURED"
    assert out["n"] == 2 and out["graded"] == 2
    assert out["success_rate"] == 0.5
    assert out["per_capability"]["skill:reframe"]["n"] == 2
