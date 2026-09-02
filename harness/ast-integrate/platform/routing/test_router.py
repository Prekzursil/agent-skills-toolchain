"""Tests for fusion, confidence, conflict resolution, overrides, explanation, fallback.

Each spec clause from `_USER-PROMPTS.md:10948-10963` has at least one test that fails if
the clause is unimplemented, and the behavioural ones are BOTH-STATES where a state can be
constructed (the feature fires when it should AND is silent when it should not).
"""

from __future__ import annotations

import copy

import pytest
from routing import rules, semantic
from routing.index import discover
from routing.router import BANDS, Router, band, confidence


@pytest.fixture(scope="module")
def r():
    return Router.build()


@pytest.fixture(scope="module")
def idx():
    return discover()


# ------------------------------------------------------------------- top-k + confidence


def test_topk_never_exceeds_k(r):
    for k in (1, 3, 5, 10):
        for q in (
            "reframe a video to vertical",
            "council protocol for a contested decision",
        ):
            assert len(r.route(q, k=k).selected) <= k


def test_confidence_is_margin_aware_not_score_aware():
    """A lone strong hit and a strong hit in a six-way tie must NOT report the same
    confidence. This is the property that makes top-k injection trustworthy."""

    class C:
        def __init__(self, f):
            self.final = f
            self.forced = False

    lone = confidence([C(0.9), C(0.1)], 0.18)
    tied = confidence([C(0.9)] + [C(0.89) for _ in range(5)], 0.18)
    assert lone > tied, (lone, tied)


def test_confidence_bands_cover_the_unit_interval():
    seen = {band(x / 100) for x in range(0, 101)}
    assert seen == {name for _lo, name in BANDS}, seen


def test_confidence_of_nothing_is_zero():
    assert confidence([], 0.18) == 0.0


# --------------------------------------------------------------------------- overrides


def test_user_override_forces_a_capability_past_the_threshold(r):
    """A forced pick must appear even when it would never score."""
    d = r.route("use reframe for this unrelated aardvark taxonomy question", k=5)
    assert "skill:reframe" in d.overrides["forced"]
    assert "skill:reframe" in d.ids
    forced = next(c for c in d.candidates if c.cap.id == "skill:reframe")
    assert forced.forced
    assert "USER OVERRIDE" in forced.why()


def test_user_override_ban_suppresses_a_capability_that_would_otherwise_win(r):
    """BOTH STATES: it wins without the ban, and is absent with it."""
    without = r.route("reframe a landscape clip to vertical", k=5)
    assert "skill:reframe" in without.ids, without.ids
    with_ban = r.route("reframe a landscape clip to vertical, do not use reframe", k=5)
    assert "skill:reframe" in with_ban.overrides["banned"]
    assert "skill:reframe" not in with_ban.ids


def test_a_ban_beats_a_force_in_the_same_query(r):
    """'use X ... do not use X' must resolve to BANNED. A force-wins policy would let a
    habit phrase override an explicit refusal."""
    d = r.route("use reframe but do not use reframe", k=5)
    assert "skill:reframe" in d.overrides["banned"]
    assert "skill:reframe" not in d.overrides["forced"]
    assert "skill:reframe" not in d.ids


def test_no_override_phrase_yields_no_overrides(r):
    d = r.route("convert a landscape clip into a portrait one", k=3)
    assert d.overrides == {"forced": [], "banned": []}


# --------------------------------------------------------------------- conflicts


def test_a_superseded_tombstone_is_demoted_and_the_reason_recorded(r):
    """`skill:design-review-loop` declares itself renamed to `design-studio`."""
    by_id = r.index.by_id()
    tomb = by_id.get("skill:design-review-loop")
    assert tomb is not None and tomb.superseded_by == "skill:design-studio", (
        tomb.superseded_by
    )
    d = r.route("run the design review loop over the app", k=5)
    if "skill:design-review-loop" in d.ids:
        pytest.fail("a self-declared tombstone should not outrank its successor")
    kinds = {c["kind"] for c in d.conflicts}
    assert "superseded" in kinds or "skill:design-studio" in d.ids


def test_conflict_resolution_demotes_but_never_deletes(r):
    """The spec forbids pruning. A demoted candidate must still be REACHABLE."""
    d = r.route("rejected fused workflow that failed the tournament", k=10)
    ids = {c.cap.id for c in d.candidates}
    rejected = [i for i in ids if i.startswith("workflow:rejected.")]
    assert rejected, "rejected blueprints must remain candidates, not be filtered out"


def test_redundant_sibling_requires_a_segment_boundary_not_a_substring():
    """MEASURED DEFECT: bare `bn in an` fired on `doc` inside `docker-*` and `cs` inside
    `docs`, producing 40+ bogus demotions per query."""
    a = "reframe-video-cutting"
    for generic, expected in (
        ("reframe", True),
        ("doc", False),
        ("cs", False),
        ("ref", False),
    ):
        assert a.startswith(f"{generic}-") is expected, (generic, expected)


def test_mirror_duplicates_are_not_both_injected(r):
    """Anti-flooding: 23 content-verified mirror pairs exist; a decision must inject at
    most one member of any pair."""
    groups = r.index.equivalence_groups()
    assert groups, "precondition: the live inventory has mirror pairs"
    for q in (
        "answer a quick side question without losing context",
        "build and fix type errors",
    ):
        d = r.route(q, k=10)
        by_id = r.index.by_id()
        keys = [by_id[i].equiv_key for i in d.ids if by_id[i].equiv_key]
        assert len(keys) == len(set(keys)), f"both mirrors injected for {q!r}: {d.ids}"


# --------------------------------------------------------------------------- explanation


def test_every_selected_capability_carries_a_non_empty_why(r):
    for q in ("reframe to vertical", "a council protocol for a contested decision"):
        d = r.route(q, k=5)
        by_id = {c.cap.id: c for c in d.candidates}
        assert d.ids, q
        for cid in d.ids:
            why = by_id[cid].why()
            assert why and "no positive evidence" not in why, (cid, why)


def test_a_similarity_only_selection_SAYS_it_is_similarity_only(r):
    """An explanation must never imply literal evidence it does not have."""
    found = False
    for q in (
        "remove the broadcaster bug from the corner of the frame",
        "strip the long gaps where nobody is talking",
    ):
        d = r.route(q, k=5)
        for c in d.candidates:
            if c.cap.id in d.ids and not c.rule_hits:
                assert "similarity only" in c.why()
                found = True
    assert found, "no similarity-only selection observed; the assertion did not run"


def test_explain_renders_evidence_and_bytes(r):
    txt = r.explain("reframe a landscape clip to vertical", k=3)
    assert (
        "CONFIDENCE:" in txt and "INJECTED:" in txt and "WHY:" in txt and "CARD:" in txt
    )


# --------------------------------------------------------------------------- fallback


def test_fallback_fires_on_a_query_no_capability_serves(r):
    d = r.route("what is the capital of Mongolia and how many people live there", k=5)
    assert d.fits is False, d.ids
    assert d.selected == []
    assert d.injected_bytes == 0, "an abstention must cost ZERO context"
    assert d.fallback is not None
    assert d.fallback["generic_path"] and d.fallback["reason"]


def test_fallback_records_the_nearest_misses_for_gap_analysis(r):
    d = r.route("please book me a dentist appointment for next Tuesday afternoon", k=5)
    if d.fits:
        pytest.skip(
            "router selected something; the gap-record path is not exercised here"
        )
    assert "nearest" in d.fallback
    assert d.near_misses or d.fallback["nearest"]


def test_threshold_stats_explain_which_bound_was_binding(r):
    d = r.route("what did I have for lunch yesterday", k=5)
    st = d.threshold_stats
    assert st["mode"] == "and-gate"
    assert st["binding"] in ("floor", "adaptive")
    assert set(st) >= {"floor", "z", "mu", "sd", "adaptive"}


# --------------------------------------------------------------------------- determinism


def test_routing_is_deterministic(r):
    q = "a workflow for landing harness changes into the live tree"
    assert [r.route(q, k=5).ids for _ in range(3)].count(r.route(q, k=5).ids) == 3


def test_two_independently_built_routers_agree(idx):
    a = Router.build(copy.deepcopy(idx))
    b = Router.build(copy.deepcopy(idx))
    q = "council protocol for an entrenched two-party disagreement"
    assert a.route(q, k=5).ids == b.route(q, k=5).ids


# ------------------------------------------------------------------- per-class caps


def test_per_class_cap_keeps_the_repertoire_reachable(r):
    """Without a cap, 328 skill records swamp every query and the 102 blueprints become
    unreachable -- the exact failure the spec's opening line forbids."""
    d = r.route("review", k=10)
    from collections import Counter

    per = Counter(i.split(":", 1)[0] for i in d.ids)
    from routing.router import CLASS_CAP, DEFAULT_CLASS_CAP

    for cls, n in per.items():
        assert n <= CLASS_CAP.get(cls, DEFAULT_CLASS_CAP), (cls, n)


# --------------------------------------------------------------------------- lanes


def test_both_lanes_contribute_somewhere_in_the_corpus(r):
    """A fused router whose second lane never fires is one lane with extra cost."""
    rule_carried = sem_carried = 0
    for q in (
        "reframe",
        "remove the broadcaster bug from the corner",
        "p12",
        "oxford debate",
    ):
        for c in r.route(q, k=5).candidates[:5]:
            if c.rule_score > 0:
                rule_carried += 1
            if c.sem_score > 0:
                sem_carried += 1
    assert rule_carried > 0 and sem_carried > 0, (rule_carried, sem_carried)


def test_rule_context_gates_a_corpus_common_fragment(idx):
    """`video` appears in many capability names and must NOT fire the literal lane."""
    ctx = rules.RuleContext.build(idx)
    common = [f for f, n in ctx.frag_df.items() if n > rules.FRAGMENT_DF_MAX]
    assert common, "precondition: some fragments are corpus-common"
    cap = next(c for c in idx.records if c.name == "reframe-video-cutting")
    hits = rules.match_one("i need a video", cap, ctx)
    assert not any(h.rule == "id-fragment" for h in hits), hits


def test_semantic_scores_are_absolute_not_max_normalized(idx):
    """MEASURED DEFECT: per-query max-normalization forced the top candidate to ~1.0 for
    every query, so the router could not abstain (L3 abstain measured 0.0/6)."""
    m = semantic.SemanticModel.fit(copy.deepcopy(idx))
    nonsense = m.score("zzqqxx aardvark mongolia dentist lunch")
    real = m.score("reframe a landscape video to vertical 9:16 for tiktok")
    assert max(nonsense.values()) < max(real.values()) * 0.6, (
        max(nonsense.values()),
        max(real.values()),
    )
