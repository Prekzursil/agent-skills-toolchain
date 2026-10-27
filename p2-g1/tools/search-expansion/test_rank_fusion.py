"""Tests for rank_fusion — written BEFORE the implementation (TDD red first).

Coverage contract: 100% line + branch for rank_fusion.py (quality.yml lane).
"""

from __future__ import annotations

import pytest

from rank_fusion import (
    FusedResult,
    extract_results,
    fuse_provider_payloads,
    normalize_url,
    reciprocal_rank_fusion,
)

# --------------------------------------------------------------------------
# normalize_url — the dedup key
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # scheme + host are case-insensitive; path is NOT
        ("HTTPS://Example.COM/Path", "https://example.com/Path"),
        # leading www. is noise
        ("https://www.example.com/a", "https://example.com/a"),
        # default ports carry no information
        ("https://example.com:443/a", "https://example.com/a"),
        ("http://example.com:80/a", "http://example.com/a"),
        # a non-default port DOES
        ("https://example.com:8443/a", "https://example.com:8443/a"),
        # fragments never identify a different document
        ("https://example.com/a#section-2", "https://example.com/a"),
        # trailing slash on a non-root path
        ("https://example.com/a/", "https://example.com/a"),
        # root path collapses to empty, so the two spellings agree
        ("https://example.com/", "https://example.com"),
        ("https://example.com", "https://example.com"),
        # tracking parameters are stripped, real ones survive and are sorted
        (
            "https://example.com/a?utm_source=x&id=7&fbclid=zz&b=2",
            "https://example.com/a?b=2&id=7",
        ),
        # a query of ONLY tracking params leaves no query string behind
        ("https://example.com/a?utm_campaign=x", "https://example.com/a"),
        # scheme-relative / bare host input still normalises
        ("example.com/a", "https://example.com/a"),
        # whitespace is not part of a URL
        ("  https://example.com/a  ", "https://example.com/a"),
    ],
)
def test_normalize_url_cases(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


def test_normalize_url_keeps_blank_query_values() -> None:
    """A blank-valued parameter is still a parameter and must survive normalisation.

    Dropping it would merge `?q=&id=7` with `?id=7` — two different requests, and on some
    sites two different pages. (Caught by the mutation check: flipping
    `keep_blank_values=True` to False left every other test green.)
    """
    assert (
        normalize_url("https://example.com/a?q=&id=7")
        == "https://example.com/a?id=7&q="
    )
    assert normalize_url("https://example.com/a?q=&id=7") != normalize_url(
        "https://example.com/a?id=7"
    )


def test_normalize_url_is_idempotent() -> None:
    once = normalize_url("HTTPS://WWW.Example.com:443/x/?utm_source=q&z=1#frag")
    assert normalize_url(once) == once


def test_normalize_url_empty_and_none_like() -> None:
    assert normalize_url("") == ""
    assert normalize_url("   ") == ""


def test_normalize_url_preserves_distinct_documents() -> None:
    """Over-aggressive normalisation silently merges different pages — guard it."""
    assert normalize_url("https://example.com/a") != normalize_url(
        "https://example.com/b"
    )
    assert normalize_url("https://a.example.com/x") != normalize_url(
        "https://b.example.com/x"
    )
    assert normalize_url("https://example.com/A") != normalize_url(
        "https://example.com/a"
    )


# --------------------------------------------------------------------------
# extract_results — provider shape adapter
# --------------------------------------------------------------------------


def test_extract_results_searxng_shape() -> None:
    """Measured live 2026-07-24 against SearXNG 2026.6.29: results[].url/.title."""
    payload = {
        "results": [
            {"url": "https://a.example/1", "title": "A", "engines": ["yandex"]},
            {"url": "https://b.example/2", "title": "B", "engines": ["quark"]},
        ],
        "unresponsive_engines": [],
    }
    got = extract_results(payload)
    assert [r["url"] for r in got] == ["https://a.example/1", "https://b.example/2"]
    assert got[0]["title"] == "A"


def test_extract_results_firecrawl_data_key() -> None:
    payload = {"success": True, "data": [{"url": "https://c.example", "title": "C"}]}
    assert [r["url"] for r in extract_results(payload)] == ["https://c.example"]


def test_extract_results_firecrawl_nested_web_key() -> None:
    payload = {"data": {"web": [{"url": "https://d.example", "title": "D"}]}}
    assert [r["url"] for r in extract_results(payload)] == ["https://d.example"]


def test_extract_results_bare_list() -> None:
    payload = [{"url": "https://e.example", "title": "E"}]
    assert [r["url"] for r in extract_results(payload)] == ["https://e.example"]


def test_extract_results_list_of_url_strings() -> None:
    assert [r["url"] for r in extract_results(["https://f.example"])] == [
        "https://f.example"
    ]


def test_extract_results_alternate_url_and_title_keys() -> None:
    payload = {"items": [{"link": "https://g.example", "name": "G"}]}
    got = extract_results(payload)
    assert got[0]["url"] == "https://g.example"
    assert got[0]["title"] == "G"


def test_extract_results_skips_entries_without_a_url() -> None:
    payload = {
        "results": [{"title": "no url"}, {"url": "https://h.example"}, {"url": ""}]
    }
    assert [r["url"] for r in extract_results(payload)] == ["https://h.example"]


def test_extract_results_empty_and_unknown_payloads() -> None:
    assert extract_results({}) == []
    assert extract_results(None) == []
    assert extract_results({"weird": 5}) == []
    assert extract_results("not a payload") == []
    assert extract_results({"results": "not-a-list"}) == []


def test_extract_results_title_defaults_to_empty_string() -> None:
    assert extract_results([{"url": "https://i.example"}])[0]["title"] == ""


def test_extract_results_skips_entries_that_are_neither_string_nor_mapping() -> None:
    payload = [1, None, ["nested"], {"url": "https://j.example"}]
    assert [r["url"] for r in extract_results(payload)] == ["https://j.example"]


def test_extract_results_skips_blank_url_strings() -> None:
    assert extract_results(["   ", "https://k.example"]) == [
        {"url": "https://k.example", "title": ""}
    ]


def test_extract_results_falls_through_a_container_with_no_usable_list() -> None:
    """`data` present but holding no recognised list must not mask a later key."""
    payload = {
        "data": {"meta": 1, "web": "not-a-list"},
        "items": [{"url": "https://l.example"}],
    }
    assert [r["url"] for r in extract_results(payload)] == ["https://l.example"]


def test_extract_results_container_with_no_usable_list_anywhere() -> None:
    assert extract_results({"data": {"meta": 1}}) == []


def test_extract_results_ignores_non_string_url_values() -> None:
    assert extract_results([{"url": 42, "link": "https://m.example"}])[0]["url"] == (
        "https://m.example"
    )


def test_extract_results_ignores_non_string_title_values() -> None:
    assert extract_results([{"url": "https://n.example", "title": 7}])[0]["title"] == ""


# --------------------------------------------------------------------------
# reciprocal_rank_fusion — the core
# --------------------------------------------------------------------------


def test_rrf_single_list_preserves_order() -> None:
    fused = reciprocal_rank_fusion({"exa": ["https://a", "https://b", "https://c"]})
    assert [f.url for f in fused] == ["https://a", "https://b", "https://c"]


def test_rrf_scores_match_the_closed_form() -> None:
    """score = sum over lists of 1/(k + rank), rank 1-based. No provider score used."""
    fused = reciprocal_rank_fusion(
        {"exa": ["https://a", "https://b"], "tavily": ["https://b", "https://a"]},
        k=60,
    )
    by_url = {f.url: f for f in fused}
    # both appear at rank 1 in one list and rank 2 in the other
    expected = 1 / 61 + 1 / 62
    assert by_url["https://a"].score == pytest.approx(expected)
    assert by_url["https://b"].score == pytest.approx(expected)


def test_rrf_agreement_beats_a_single_top_hit() -> None:
    """The property that makes RRF worth having: consensus outranks one loud vote."""
    fused = reciprocal_rank_fusion(
        {
            "exa": ["https://loud", "https://agreed"],
            "tavily": ["https://x", "https://agreed"],
            "searxng": ["https://y", "https://agreed"],
        }
    )
    assert fused[0].url == "https://agreed"
    assert len(fused[0].sources) == 3


def test_rrf_records_provenance_and_best_rank() -> None:
    fused = reciprocal_rank_fusion(
        {"exa": ["https://a", "https://b"], "searxng": ["https://b"]}
    )
    b = next(f for f in fused if f.url == "https://b")
    assert b.sources == ("exa", "searxng")
    assert b.ranks == {"exa": 2, "searxng": 1}


def test_rrf_duplicate_url_within_one_list_counts_once_at_best_rank() -> None:
    """A provider repeating a URL must not be able to inflate its own score."""
    fused = reciprocal_rank_fusion({"exa": ["https://a", "https://a", "https://b"]})
    a = next(f for f in fused if f.url == "https://a")
    assert a.ranks == {"exa": 1}
    assert a.score == pytest.approx(1 / 61)
    assert len(fused) == 2


def test_rrf_dedups_across_providers_by_normalized_url() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": ["https://www.Example.com/a/?utm_source=nl"],
            "tavily": ["https://example.com/a#top"],
        }
    )
    assert len(fused) == 1
    assert fused[0].url == "https://example.com/a"
    assert fused[0].sources == ("exa", "tavily")


def test_rrf_display_url_keeps_the_first_seen_original() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": ["https://www.example.com/a?utm_source=nl"],
            "tavily": ["https://example.com/a"],
        }
    )
    assert fused[0].display_url == "https://www.example.com/a?utm_source=nl"


def test_rrf_k_changes_how_flat_the_curve_is() -> None:
    """Small k sharpens the top-rank advantage; large k flattens it."""
    lists = {"a": ["https://1", "https://2"]}
    sharp = reciprocal_rank_fusion(lists, k=1)
    flat = reciprocal_rank_fusion(lists, k=1000)
    sharp_gap = sharp[0].score - sharp[1].score
    flat_gap = flat[0].score - flat[1].score
    assert sharp_gap > flat_gap


def test_rrf_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError, match="k must be > 0"):
        reciprocal_rank_fusion({"a": ["https://1"]}, k=0)
    with pytest.raises(ValueError, match="k must be > 0"):
        reciprocal_rank_fusion({"a": ["https://1"]}, k=-5)


def test_rrf_limit_truncates_after_ranking_not_before() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": ["https://x", "https://agreed"],
            "tavily": ["https://y", "https://agreed"],
        },
        limit=1,
    )
    assert len(fused) == 1
    assert fused[0].url == "https://agreed"


def test_rrf_limit_of_zero_returns_nothing() -> None:
    assert reciprocal_rank_fusion({"exa": ["https://x"]}, limit=0) == []


def test_rrf_negative_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="limit must be >= 0"):
        reciprocal_rank_fusion({"exa": ["https://x"]}, limit=-1)


def test_rrf_empty_inputs() -> None:
    assert reciprocal_rank_fusion({}) == []
    assert reciprocal_rank_fusion({"exa": [], "tavily": []}) == []


def test_rrf_ignores_entries_with_unusable_urls() -> None:
    fused = reciprocal_rank_fusion({"exa": ["", "   ", None, 42, "https://ok"]})
    assert [f.url for f in fused] == ["https://ok"]
    # the skipped entries must not shift the surviving one's rank
    assert fused[0].ranks == {"exa": 1}


def test_rrf_accepts_dict_results_and_carries_titles() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": [{"url": "https://a", "title": "Alpha"}],
            "tavily": [{"url": "https://a"}],
        }
    )
    assert fused[0].title == "Alpha"


def test_rrf_title_falls_back_to_a_later_provider() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": [{"url": "https://a", "title": ""}],
            "tavily": [{"url": "https://a", "title": "T"}],
        }
    )
    assert fused[0].title == "T"


def test_rrf_ordering_is_deterministic_for_tied_scores() -> None:
    """Ties must break the same way every run, or the ranking is not reproducible."""
    lists = {"a": ["https://z", "https://y"], "b": ["https://y", "https://z"]}
    runs = [[f.url for f in reciprocal_rank_fusion(lists)] for _ in range(5)]
    assert all(r == runs[0] for r in runs)
    # tie -> lexicographic by normalised url, so the order is inspectable
    assert runs[0] == ["https://y", "https://z"]


def test_rrf_result_is_frozen() -> None:
    fused = reciprocal_rank_fusion({"exa": ["https://a"]})
    assert isinstance(fused[0], FusedResult)
    with pytest.raises(AttributeError):
        fused[0].score = 99.0  # type: ignore[misc]


def test_rrf_scores_descend() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": ["https://a", "https://b", "https://c"],
            "tavily": ["https://c", "https://a"],
        }
    )
    scores = [f.score for f in fused]
    assert scores == sorted(scores, reverse=True)


def test_rrf_provider_order_does_not_change_the_ranking() -> None:
    """Fusion must be commutative in its providers, else results depend on dict order."""
    a = reciprocal_rank_fusion({"exa": ["https://1", "https://2"], "tv": ["https://2"]})
    b = reciprocal_rank_fusion({"tv": ["https://2"], "exa": ["https://1", "https://2"]})
    assert [f.url for f in a] == [f.url for f in b]
    assert [f.score for f in a] == [f.score for f in b]


# --------------------------------------------------------------------------
# fuse_provider_payloads — end-to-end over raw provider responses
# --------------------------------------------------------------------------


def test_fuse_provider_payloads_end_to_end() -> None:
    searxng = {
        "results": [
            {"url": "https://ru.wikipedia.org/wiki/X", "title": "X ru"},
            {"url": "https://habr.com/ru/articles/1/", "title": "Habr"},
        ]
    }
    exa = {
        "results": [{"url": "https://habr.com/ru/articles/1", "title": "Habr (exa)"}]
    }
    firecrawl = {"data": [{"url": "https://www.habr.com/ru/articles/1?utm_source=x"}]}

    fused = fuse_provider_payloads(
        {"searxng": searxng, "exa": exa, "firecrawl": firecrawl}
    )
    assert fused[0].url == "https://habr.com/ru/articles/1"
    assert fused[0].sources == ("searxng", "exa", "firecrawl")
    assert fused[0].title == "Habr"
    assert len(fused) == 2


def test_fuse_provider_payloads_passes_k_and_limit_through() -> None:
    payloads = {
        "a": {"results": [{"url": "https://1"}, {"url": "https://2"}]},
        "b": {"results": [{"url": "https://2"}]},
    }
    assert len(fuse_provider_payloads(payloads, limit=1)) == 1
    sharp = fuse_provider_payloads(payloads, k=1)
    flat = fuse_provider_payloads(payloads, k=500)
    assert sharp[0].score > flat[0].score


def test_fuse_provider_payloads_tolerates_a_dead_provider() -> None:
    """One provider erroring out must not sink the fusion."""
    fused = fuse_provider_payloads(
        {"exa": {"results": [{"url": "https://a"}]}, "tavily": {"error": "429"}}
    )
    assert [f.url for f in fused] == ["https://a"]
    assert fused[0].sources == ("exa",)


def test_fuse_provider_payloads_empty() -> None:
    assert fuse_provider_payloads({}) == []
