"""Tests for query_plan — written BEFORE the implementation (TDD red first).

Coverage contract: 100% line + branch for query_plan.py (quality.yml lane).

The decompose->translate->dedup borrow adds a PURE planning sibling to rank_fusion:
`translate_for_provider`/`plan_sources` turn one decomposed sub-query into the concrete
per-provider calls (SearXNG regional bangs vs a plain query), and `fuse_decomposed` folds
the already-fused per-sub-query rankings into one — REUSING `reciprocal_rank_fusion`'s dedup
rather than rebuilding it. A synthetic `engines` table keeps the routing assertions
independent of the live measured `REGIONAL_ENGINES`, with one integration test pinned to it.
"""

from __future__ import annotations

import pytest

from query_plan import (
    DEFAULT_PROVIDERS,
    SourcePlan,
    SubQuery,
    fuse_decomposed,
    plan_sources,
    translate_for_provider,
)
from rank_fusion import FusedResult, reciprocal_rank_fusion
from searxng_config import EngineSpec

# A controlled table: two working CN engines, one working RU engine, one BLOCKED CN engine
# (which `enabled_specs` must filter out before the region match ever runs).
FAKE_ENGINES: tuple[EngineSpec, ...] = (
    EngineSpec("alpha", "al", "CN", "works", "cn-a"),
    EngineSpec("beta", "bt", "CN", "works", "cn-b"),
    EngineSpec("gamma", "gm", "RU", "works", "ru-a"),
    EngineSpec("delta", "dl", "CN", "blocked", "cn-broken"),
)


# --------------------------------------------------------------------------
# constants + dataclasses
# --------------------------------------------------------------------------


def test_default_providers_are_the_four_search_rails() -> None:
    assert DEFAULT_PROVIDERS == ("searxng", "exa", "tavily", "firecrawl")


def test_subquery_is_frozen_and_carries_locale_hints() -> None:
    sq = SubQuery("weather", region="CN", lang="zh")
    assert (sq.text, sq.region, sq.lang) == ("weather", "CN", "zh")
    with pytest.raises(AttributeError):
        sq.text = "changed"  # type: ignore[misc]


def test_subquery_region_and_lang_default_to_none() -> None:
    sq = SubQuery("weather")
    assert sq.region is None
    assert sq.lang is None


def test_sourceplan_is_frozen_with_optional_engine_and_bang() -> None:
    plan = SourcePlan("searxng", "weather", engine="alpha", bang="!al")
    assert (plan.provider, plan.query, plan.engine, plan.bang) == (
        "searxng",
        "weather",
        "alpha",
        "!al",
    )
    plain = SourcePlan("exa", "weather")
    assert plain.engine is None and plain.bang is None
    with pytest.raises(AttributeError):
        plan.query = "changed"  # type: ignore[misc]


# --------------------------------------------------------------------------
# translate_for_provider — the per-provider translate stage
# --------------------------------------------------------------------------


def test_searxng_regional_query_fans_out_to_working_engines_only() -> None:
    sq = SubQuery("factory output", region="CN")
    plans = translate_for_provider(sq, "searxng", engines=FAKE_ENGINES)
    # delta is CN but BLOCKED -> excluded; gamma is working but RU -> excluded.
    assert [(p.engine, p.bang) for p in plans] == [
        ("alpha", "!al"),
        ("beta", "!bt"),
    ]
    assert all(p.provider == "searxng" and p.query == "factory output" for p in plans)


def test_region_match_is_case_insensitive() -> None:
    sq = SubQuery("factory output", region="cn")
    plans = translate_for_provider(sq, "searxng", engines=FAKE_ENGINES)
    assert [p.engine for p in plans] == ["alpha", "beta"]


def test_searxng_without_region_is_a_single_plain_query() -> None:
    plans = translate_for_provider(SubQuery("weather"), "searxng", engines=FAKE_ENGINES)
    assert plans == (SourcePlan("searxng", "weather"),)


def test_searxng_blank_region_is_a_single_plain_query() -> None:
    sq = SubQuery("weather", region="   ")
    plans = translate_for_provider(sq, "searxng", engines=FAKE_ENGINES)
    assert plans == (SourcePlan("searxng", "weather"),)


def test_searxng_region_with_no_working_engine_falls_back_to_plain() -> None:
    sq = SubQuery("weather", region="ZZ")
    plans = translate_for_provider(sq, "searxng", engines=FAKE_ENGINES)
    assert plans == (SourcePlan("searxng", "weather"),)


@pytest.mark.parametrize("region", [None, "", "   ", "ZZ"])
def test_regional_specs_returns_the_documented_empty_tuple_not_none(
    region: str | None,
) -> None:
    """The docstring promises an empty TUPLE. `None` is falsy too, so the public path could
    not tell them apart (mutation-check survivor at HEAD); pin the promised type."""
    from query_plan import _regional_specs

    assert _regional_specs(region, FAKE_ENGINES) == ()


def test_non_searxng_provider_ignores_region_and_emits_one_plain_query() -> None:
    sq = SubQuery("factory output", region="CN")
    plans = translate_for_provider(sq, "exa", engines=FAKE_ENGINES)
    assert plans == (SourcePlan("exa", "factory output"),)


def test_real_regional_table_routes_cn_to_working_engines_never_broken() -> None:
    # Integration: the default `engines=REGIONAL_ENGINES`. baidu/sogou are the measured
    # BLOCKED CN engines and must never appear; the working CN engines must.
    plans = translate_for_provider(SubQuery("q", region="CN"), "searxng")
    engines = {p.engine for p in plans}
    assert {"quark", "360search", "baidu kaifa"} <= engines
    assert "baidu" not in engines
    assert "sogou" not in engines
    assert all(p.bang is not None and p.bang.startswith("!") for p in plans)


# --------------------------------------------------------------------------
# plan_sources — fan a sub-query over every provider
# --------------------------------------------------------------------------


def test_plan_sources_concatenates_every_provider_translation() -> None:
    sq = SubQuery("factory output", region="CN")
    plans = plan_sources(sq, engines=FAKE_ENGINES)
    # searxng fans to 2 working CN engines; each of exa/tavily/firecrawl adds one plain.
    assert [p.provider for p in plans] == [
        "searxng",
        "searxng",
        "exa",
        "tavily",
        "firecrawl",
    ]
    assert [p.engine for p in plans] == ["alpha", "beta", None, None, None]


def test_plan_sources_honors_custom_provider_order() -> None:
    sq = SubQuery("weather")
    plans = plan_sources(sq, providers=("exa", "searxng"), engines=FAKE_ENGINES)
    assert plans == (
        SourcePlan("exa", "weather"),
        SourcePlan("searxng", "weather"),
    )


# --------------------------------------------------------------------------
# fuse_decomposed — re-dedup across sub-queries by REUSING RRF
# --------------------------------------------------------------------------


def _fusion(provider: str, *entries: dict[str, str]) -> list[FusedResult]:
    return reciprocal_rank_fusion({provider: list(entries)})


def test_fuse_decomposed_merges_a_url_seen_in_two_subqueries() -> None:
    sq0 = _fusion(
        "searxng",
        {"url": "https://a.com/x", "title": "A doc"},
        {"url": "https://b.com/y", "title": "B doc"},
    )
    sq1 = _fusion(
        "exa",
        {"url": "https://A.com/x", "title": "A doc alt"},
        {"url": "https://c.com/z", "title": "C doc"},
    )
    fused = fuse_decomposed([sq0, sq1])
    assert [r.url for r in fused] == [
        "https://a.com/x",
        "https://b.com/y",
        "https://c.com/z",
    ]
    top = fused[0]
    assert top.sources == ("subquery-0", "subquery-1")
    assert top.display_url == "https://a.com/x"  # first spelling seen wins
    assert top.title == "A doc"
    assert top.score == pytest.approx(2 / 61)


def test_fuse_decomposed_respects_limit() -> None:
    sq0 = _fusion("searxng", {"url": "https://a.com/x", "title": "A"})
    sq1 = _fusion("exa", {"url": "https://a.com/x", "title": "A"})
    fused = fuse_decomposed([sq0, sq1], limit=1)
    assert len(fused) == 1
    assert fused[0].url == "https://a.com/x"


def test_fuse_decomposed_threads_custom_k() -> None:
    sq0 = _fusion("searxng", {"url": "https://a.com/x", "title": "A"})
    sq1 = _fusion("exa", {"url": "https://a.com/x", "title": "A"})
    fused = fuse_decomposed([sq0, sq1], k=1)
    assert fused[0].score == pytest.approx(1.0)  # 1/(1+1) + 1/(1+1)


def test_fuse_decomposed_of_nothing_is_empty() -> None:
    assert fuse_decomposed([]) == []


def test_fuse_decomposed_carries_snippets_through_the_second_fusion() -> None:
    """The second RRF stage must not strip what the first one carried, or no reranker
    can run after a decomposed query either."""
    sq0 = _fusion("searxng", {"url": "https://a.com/x", "title": "A", "content": "sx"})
    sq1 = _fusion("exa", {"url": "https://b.com/y", "title": "B", "text": "exa"})
    fused = fuse_decomposed([sq0, sq1])
    assert {r.url: r.snippet for r in fused} == {
        "https://a.com/x": "sx",
        "https://b.com/y": "exa",
    }
