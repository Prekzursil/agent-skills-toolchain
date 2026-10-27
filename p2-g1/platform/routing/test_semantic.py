"""Tests for the hermetic recall lane and the rule lane's IDF gates."""

from __future__ import annotations

import copy

import pytest
from routing import rules, semantic
from routing.index import Capability, discover


@pytest.fixture(scope="module")
def live():
    return discover()


@pytest.fixture(scope="module")
def model(live):
    return semantic.SemanticModel.fit(copy.deepcopy(live))


@pytest.fixture(scope="module")
def ctx(live):
    return rules.RuleContext.build(live)


# --------------------------------------------------------------------------- hermetic


def test_the_lane_makes_no_network_call(monkeypatch, live):
    """The whole justification for this lane is that it can back a CI gate
    (`ci-hygiene.md` 2). Any socket use would void that."""
    import socket

    def boom(*_a, **_k):  # pragma: no cover - must never be reached
        raise AssertionError("the semantic lane opened a socket")

    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    m = semantic.SemanticModel.fit(copy.deepcopy(live))
    assert m.top("reframe a landscape video to vertical", k=3)


# --------------------------------------------------------------------------- BM25


def test_idf_is_never_negative(model):
    """The textbook `log((N-df)/df)` form goes NEGATIVE past df > N/2, which would PENALIZE
    a capability for containing a common word. The Lucene form must not."""
    assert model.idf, "model has no vocabulary"
    assert min(model.idf.values()) >= 0.0, min(model.idf.values())


def test_a_rare_term_outweighs_a_common_one(model):
    """IDF is the difference between evidence and coincidence in this corpus."""
    rare = min(model.df, key=lambda t: model.df[t] if len(t) > 5 else 10**9)
    common = max(model.df, key=lambda t: model.df[t])
    assert model.idf[rare] > model.idf[common], (rare, common)


def test_scores_are_absolute_so_nonsense_scores_low(model):
    """MEASURED DEFECT: per-query max-normalization forced the top candidate to ~1.0 for
    every query, and the L3 abstain rate measured 0.0/6 as a direct consequence."""
    nonsense = max(model.score("zzqqxx wibblefrotz aardvark mongolia").values())
    real = max(
        model.score("reframe a landscape video to a vertical 9:16 crop").values()
    )
    assert nonsense < 0.5, nonsense
    assert real > nonsense * 1.5, (real, nonsense)


def test_scores_stay_within_the_unit_interval(model):
    for q in ("reframe video vertical", "council protocol dissent", "a"):
        vals = list(model.score(q).values())
        assert min(vals) >= 0.0 and max(vals) <= 1.0 + 1e-9, (q, min(vals), max(vals))


def test_an_all_unknown_query_degrades_instead_of_dividing_by_zero(model):
    """`ceiling` is 0 when no query term exists in the corpus; the lane must still answer."""
    s = model.score("zzzqqq xxwwvv yyuuii")
    assert len(s) == model.n
    assert max(s.values()) < 0.4


def test_ranking_is_deterministic_including_ties(model):
    q = "review"
    assert model.top(q, k=10) == model.top(q, k=10)
    ids = [i for i, _s in model.top(q, k=10)]
    assert ids == sorted(ids, key=lambda i: (-dict(model.top(q, k=10))[i], i))


# --------------------------------------------------------------------------- ngram lane


def test_char_ngram_bridges_inflection(model):
    """ "docking" must reach a record that says "dock"; this is the lane's whole job."""
    g = semantic.ngrams("docking")
    h = semantic.ngrams("dock the ligand")
    assert set(g) & set(h), "no shared 4-gram between docking and dock"


def test_ngram_lane_can_be_disabled_and_it_matters(live):
    """Its ablation measured -0.064 recall when removed, so it must be doing something."""
    on = semantic.SemanticModel.fit(copy.deepcopy(live), use_ngram=True)
    off = semantic.SemanticModel.fit(copy.deepcopy(live), use_ngram=False)
    q = "removing a broadcaster bug from the corner of a clip"
    assert on.top(q, k=5) != off.top(q, k=5)


def test_ngrams_of_empty_text_is_empty():
    assert semantic.ngrams("") == {}
    assert semantic.ngrams("!!!") == {}


# --------------------------------------------------------------------- concept expansion


def test_expansion_is_OFF_by_default_on_a_measured_negative_result():
    """Ablation measured recall 0.5196 with expansion vs 0.5392 without (delta +0.0196).
    Shipping it ON because the effort was already spent is the decorative-feature failure
    this program keeps finding."""
    assert semantic.EXPANSION_DEFAULT is False
    assert semantic.SemanticModel().use_expansion is False


def test_expansion_never_outweighs_a_term_the_user_actually_typed():
    bag = semantic.expand(["vertical", "reframe"])
    assert bag["vertical"] == 1.0 and bag["reframe"] == 1.0
    bridged = [t for t, w in bag.items() if w < 1.0]
    assert bridged, "expansion produced no bridged terms"
    assert max(bag[t] for t in bridged) <= semantic.EXPANSION_WEIGHT


def test_expansion_does_not_downgrade_a_typed_term_that_is_also_a_synonym():
    """`max`, not `+=`: a bridge must never reweight the user's own vocabulary."""
    bag = semantic.expand(["subtitle", "caption"])
    assert bag["caption"] == 1.0


# --------------------------------------------------------------------------- rule lane


def test_exact_name_beats_any_stack_of_weak_signals():
    strong = rules.score_of([rules.RuleHit("exact-name", rules.W_EXACT_NAME, "x")])
    weak = rules.score_of(
        [
            rules.RuleHit("tag", rules.W_TAG, "t"),
            rules.RuleHit("category", rules.W_CATEGORY, "c"),
            rules.RuleHit("family", rules.W_FAMILY, "f"),
            rules.RuleHit("class-hint", rules.W_CLASS_HINT, "h"),
        ]
    )
    assert strong > weak, (strong, weak)


def test_diminishing_returns_prevents_weak_signal_stacking():
    one = rules.score_of([rules.RuleHit("tag", 0.3, "a")])
    four = rules.score_of([rules.RuleHit("tag", 0.3, str(i)) for i in range(4)])
    assert four < one * 2.0, (one, four)


def test_an_anti_trigger_demotes_below_zero():
    s = rules.score_of(
        [
            rules.RuleHit("tag", rules.W_TAG, "t"),
            rules.RuleHit("anti-trigger", rules.W_ANTI_TRIGGER, "a"),
        ]
    )
    assert s < 0, s


def _cap(**kw):
    base = dict(
        id="skill:zzz",
        cls="skill",
        name="zzz",
        anchor=__file__,
        routing_text="",
        card="c",
        card_bytes=1,
    )
    base.update(kw)
    return Capability(**base)


def test_id_fragment_weight_scales_with_name_coverage(ctx):
    """MEASURED DEFECT: an unscaled fragment ("tiktok" of "tiktok-public-research") beat
    the top semantic match. Evidence must be scaled by how much of the name it explains."""
    whole = _cap(id="skill:calibration", name="calibration")
    part = _cap(
        id="skill:calibration-public-research-tooling",
        name="calibration-public-research-tooling",
    )
    hw = [
        h
        for h in rules.match_one("do a calibration", whole, ctx)
        if h.rule == "id-fragment"
    ]
    hp = [
        h
        for h in rules.match_one("do a calibration", part, ctx)
        if h.rule == "id-fragment"
    ]
    assert hp, "the fragment lane must still fire for the long name"
    if hw:
        assert hw[0].weight > hp[0].weight
    assert hp[0].weight < rules.W_ID_SUBSTRING


def test_trigger_overlap_is_normalized_by_the_QUERY_not_the_phrase(ctx):
    """A long trigger that covers the whole query must fire. Phrase-normalization made
    that impossible and cost `skill:reframe` its own query."""
    long_trigger = (
        "the user wants to convert, reframe, or crop a landscape video to vertical, follow "
        "a moving subject in a vertical crop, or turn long horizontal footage into a "
        "portrait clip"
    )
    cov, ev = rules._phrase_overlap(
        {"landscape", "video", "vertical"}, long_trigger, ctx
    )
    assert cov >= rules.TRIGGER_MIN_COVERAGE, (cov, ev)


def test_trigger_overlap_is_low_for_an_unrelated_query(ctx):
    """Control for the test above: query-normalization must not make everything fire."""
    cov, _ev = rules._phrase_overlap(
        {"mongolia", "capital", "population"},
        "reframe a landscape video to vertical",
        ctx,
    )
    assert cov < rules.TRIGGER_MIN_COVERAGE, cov


def test_rule_context_is_reusable_and_deterministic(live):
    a = rules.RuleContext.build(live)
    b = rules.RuleContext.build(live)
    assert a.frag_df == b.frag_df
    assert a.default_idf == b.default_idf


def test_unseen_query_terms_get_the_maximum_idf(ctx):
    assert ctx.weight("zzqqxxwwvv") == ctx.default_idf
    assert ctx.default_idf >= max(ctx.idf.values())
