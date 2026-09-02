"""Tests for rank_fusion — written BEFORE the implementation (TDD red first).

Coverage contract: 100% line + branch for rank_fusion.py (quality.yml lane).
"""

from __future__ import annotations

import pytest

from rank_fusion import (
    DEFAULT_DIVERSITY_WINDOW,
    DEFAULT_MAX_PER_HOST,
    DEFAULT_NEAR_DUP_THRESHOLD,
    MAX_SNIPPET_CHARS,
    FusedResult,
    diversify,
    extract_results,
    fuse_provider_payloads,
    host_key,
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
        {"url": "https://k.example", "title": "", "snippet": ""}
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
# extract_results — snippet carry (the prerequisite for any downstream reranker)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "key",
    ["snippet", "description", "content", "text", "summary", "markdown"],
)
def test_extract_results_carries_a_snippet_from_each_provider_key(key: str) -> None:
    """SearXNG/Tavily use `content`, Exa `text`/`summary`, Firecrawl
    `description`/`markdown`. Any of them must surface as `snippet`."""
    got = extract_results([{"url": "https://s.example", key: "some passage"}])
    assert got[0]["snippet"] == "some passage"


def test_extract_results_snippet_key_precedence_is_the_documented_order() -> None:
    """The short, query-dependent field must win over a page body when both exist."""
    firecrawl = {
        "url": "https://s.example",
        "description": "meta",
        "markdown": "# body",
    }
    assert extract_results([firecrawl])[0]["snippet"] == "meta"
    generic = {"url": "https://s.example", "content": "c", "snippet": "s", "text": "t"}
    assert extract_results([generic])[0]["snippet"] == "s"


def test_extract_results_snippet_defaults_to_empty_string() -> None:
    assert extract_results([{"url": "https://s.example"}])[0]["snippet"] == ""
    assert extract_results(["https://s.example"])[0]["snippet"] == ""


def test_extract_results_snippet_skips_non_string_and_blank_values() -> None:
    """Exa returns `summary: null` unless asked; a blank field is not a snippet."""
    entry = {"url": "https://s.example", "content": None, "text": "   ", "summary": "S"}
    assert extract_results([entry])[0]["snippet"] == "S"


def test_extract_results_snippet_is_whitespace_collapsed() -> None:
    entry = {"url": "https://s.example", "content": "  a\n\n  b\t\tc  "}
    assert extract_results([entry])[0]["snippet"] == "a b c"


def test_extract_results_snippet_is_capped_so_page_bodies_are_never_carried() -> None:
    """Firecrawl `markdown` and Exa `text` can be whole pages; carry ~500 chars only."""
    assert MAX_SNIPPET_CHARS == 500
    got = extract_results([{"url": "https://s.example", "markdown": "x" * 2000}])[0]
    assert len(got["snippet"]) == MAX_SNIPPET_CHARS
    # a cut that lands on a word gap does not carry the dangling space
    words = extract_results([{"url": "https://s.example", "text": "word " * 1000}])
    assert len(words[0]["snippet"]) == MAX_SNIPPET_CHARS - 1
    assert words[0]["snippet"].endswith("word")


def test_extract_results_snippet_at_exactly_the_cap_is_untouched() -> None:
    exact = "x" * MAX_SNIPPET_CHARS
    got = extract_results([{"url": "https://s.example", "content": exact}])[0]
    assert got["snippet"] == exact


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


# --------------------------------------------------------------------------
# reciprocal_rank_fusion — snippet rule: best-ranking provider's snippet wins
# --------------------------------------------------------------------------


def test_fused_result_snippet_defaults_to_empty_for_existing_constructors() -> None:
    """Adding the field must not break anyone building FusedResult positionally."""
    r = FusedResult("https://a", "https://a", "T", 1.0, ("exa",), {"exa": 1})
    assert r.snippet == ""


def test_rrf_snippet_comes_from_the_provider_that_ranked_the_url_best() -> None:
    """Snippets are query-dependent: the engine that ranked a page highest is the one
    whose passage matched the query best. Provider order must not change the pick."""
    exa = [{"url": "https://other"}, {"url": "https://a", "snippet": "from exa (#2)"}]
    tavily = [{"url": "https://a", "snippet": "from tavily (#1)"}]
    for rankings in ({"exa": exa, "tavily": tavily}, {"tavily": tavily, "exa": exa}):
        fused = reciprocal_rank_fusion(rankings)
        a = next(f for f in fused if f.url == "https://a")
        assert a.snippet == "from tavily (#1)"


def test_rrf_snippet_falls_back_past_a_best_ranked_provider_with_none() -> None:
    fused = reciprocal_rank_fusion(
        {
            "tavily": [{"url": "https://a"}],  # rank 1, no snippet -> does not compete
            "exa": [{"url": "https://x"}, {"url": "https://a", "snippet": "exa #2"}],
        }
    )
    a = next(f for f in fused if f.url == "https://a")
    assert a.snippet == "exa #2"


def test_rrf_snippet_tie_on_rank_goes_to_the_first_consulted_provider() -> None:
    fused = reciprocal_rank_fusion(
        {
            "searxng": [{"url": "https://a", "content": "searxng #1"}],
            "exa": [{"url": "https://a", "text": "exa #1"}],
        }
    )
    assert fused[0].snippet == "searxng #1"


def test_rrf_snippet_is_decided_at_the_counted_rank_not_a_later_repeat() -> None:
    """A provider repeating a URL cannot inflate its rank; it cannot rewrite its snippet
    either — the occurrence that earned the rank is the one that speaks."""
    fused = reciprocal_rank_fusion(
        {
            "exa": [
                {"url": "https://a", "snippet": "first occurrence"},
                {"url": "https://b"},
                {"url": "https://a", "snippet": "late repeat"},
            ]
        }
    )
    a = next(f for f in fused if f.url == "https://a")
    assert a.snippet == "first occurrence"


def test_rrf_snippet_is_empty_when_no_provider_supplied_one() -> None:
    fused = reciprocal_rank_fusion(
        {"exa": ["https://a"], "tavily": [{"url": "https://a"}]}
    )
    assert fused[0].snippet == ""


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


def test_fuse_provider_payloads_carries_snippets_end_to_end() -> None:
    """SearXNG `content` and Exa `text` both reach the FusedResult as `snippet`."""
    searxng = {"results": [{"url": "https://a", "title": "A", "content": "sx passage"}]}
    exa = {"results": [{"url": "https://b", "title": "B", "text": "exa passage"}]}
    fused = fuse_provider_payloads({"searxng": searxng, "exa": exa})
    by_url = {f.url: f.snippet for f in fused}
    assert by_url == {"https://a": "sx passage", "https://b": "exa passage"}


# --------------------------------------------------------------------------
# host_key — the registrable-host approximation behind the diversity cap
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://example.com/a", "example.com"),
        # www. and case are noise (mirrors normalize_url, defensively re-applied)
        ("https://www.example.com/a", "example.com"),
        ("https://WWW.Example.COM/a", "example.com"),
        # subdomains fold into the parent: language editions are the common repeat
        ("https://docs.python.org/3/", "python.org"),
        ("https://ru.wikipedia.org/wiki/X", "wikipedia.org"),
        ("https://a.b.c.example.com/x", "example.com"),
        # two-letter ccTLD under a generic second-level label -> keep three labels
        ("https://news.bbc.co.uk/x", "bbc.co.uk"),
        ("https://bbc.co.uk/x", "bbc.co.uk"),
        ("https://finance.sina.com.cn/x", "sina.com.cn"),
        ("https://www.go.kr/x", "go.kr"),
        # ...but a two-letter TLD with an ordinary second label is a normal domain
        ("https://foo.example.co/x", "example.co"),
        # documented over-merge: shared-hosting parents count as ONE host
        ("https://alice.github.io/x", "github.io"),
        # ports and userinfo are not part of the host
        ("https://user:pw@example.com:8443/x", "example.com"),
        # IP literals and single-label hosts are used whole
        ("https://192.168.1.10:8080/x", "192.168.1.10"),
        ("https://localhost:8890/search", "localhost"),
        ("https://[::1]/x", "::1"),
        # a URL that carries no host at all still yields a (shared) key
        ("https:///no-host", ""),
    ],
)
def test_host_key_cases(url: str, expected: str) -> None:
    assert host_key(url) == expected


# --------------------------------------------------------------------------
# diversify — host cap + near-duplicate demotion (re-ordering only)
# --------------------------------------------------------------------------


def _fr(
    url: str, title: str = "", snippet: str = "", score: float = 1.0
) -> FusedResult:
    return FusedResult(url, url, title, score, ("t",), {"t": 1}, snippet)


def test_diversify_defaults_are_the_documented_values() -> None:
    assert DEFAULT_MAX_PER_HOST == 2
    assert DEFAULT_NEAR_DUP_THRESHOLD == 0.8
    assert DEFAULT_DIVERSITY_WINDOW == 10


def test_diversify_caps_results_per_host_within_the_window() -> None:
    fused = [
        _fr("https://a.com/1"),
        _fr("https://a.com/2"),
        _fr("https://a.com/3"),
        _fr("https://b.com/1"),
    ]
    out = diversify(fused)
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://a.com/2",
        "https://b.com/1",
        "https://a.com/3",
    ]


def test_diversify_host_cap_folds_subdomains_into_one_host() -> None:
    fused = [
        _fr("https://en.wikipedia.org/1"),
        _fr("https://ru.wikipedia.org/2"),
        _fr("https://zh.wikipedia.org/3"),
        _fr("https://mojeek.com/1"),
    ]
    assert [r.url for r in diversify(fused)][2] == "https://mojeek.com/1"


def test_diversify_demotes_never_drops() -> None:
    fused = [_fr(f"https://a.com/{i}") for i in range(6)]
    out = diversify(fused)
    assert len(out) == len(fused)
    assert {r.url for r in out} == {r.url for r in fused}


def test_diversify_is_a_reordering_only_scores_and_objects_untouched() -> None:
    """Demotion must leave the RRF score visible: a caller can still see WHY the
    original order was what it was, and a non-monotonic score column is the trace."""
    fused = [
        _fr("https://a.com/1", score=0.5),
        _fr("https://a.com/2", score=0.4),
        _fr("https://a.com/3", score=0.3),
        _fr("https://b.com/1", score=0.2),
    ]
    out = diversify(fused)
    assert [r.score for r in out] == [0.5, 0.4, 0.2, 0.3]
    assert all(any(o is f for f in fused) for o in out)


def test_diversify_tail_keeps_original_relative_order() -> None:
    """Everything outside the window — demoted or simply beyond it — stays in RRF order."""
    fused = [
        _fr("https://a.com/1"),
        _fr("https://a.com/2"),
        _fr("https://a.com/3"),  # demoted (host cap)
        _fr("https://b.com/1"),
        _fr("https://c.com/1"),  # beyond a window of 3
        _fr("https://d.com/1"),
    ]
    out = diversify(fused, window=3)
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://a.com/2",
        "https://b.com/1",
        "https://a.com/3",
        "https://c.com/1",
        "https://d.com/1",
    ]


def test_diversify_promotes_a_diverse_result_from_beyond_the_window() -> None:
    """The MMR-style payoff: a fresh host at position 4 rises into a window of 3."""
    fused = [_fr(f"https://a.com/{i}") for i in range(3)] + [_fr("https://b.com/1")]
    out = diversify(fused, window=3)
    assert [r.url for r in out][:3] == [
        "https://a.com/0",
        "https://a.com/1",
        "https://b.com/1",
    ]


def test_diversify_rules_do_not_apply_past_the_window() -> None:
    """With the window already full, later same-host results are neither examined nor
    reordered — the cap is a property of the top of the list, not of the whole list."""
    fused = [
        _fr("https://a.com/1"),
        _fr("https://b.com/1"),
        _fr("https://a.com/2"),
        _fr("https://a.com/3"),
        _fr("https://a.com/4"),
    ]
    assert [r.url for r in diversify(fused, window=2)] == [r.url for r in fused]


def test_diversify_near_duplicate_title_plus_snippet_is_demoted() -> None:
    """Jaccard 5/6 > 0.8 -> the second is a near-duplicate of the first."""
    fused = [
        _fr("https://a.com/1", "alpha beta gamma", "delta epsilon zeta"),
        _fr("https://b.com/1", "alpha beta gamma", "delta epsilon"),
        _fr("https://c.com/1", "something else entirely"),
    ]
    out = diversify(fused)
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://c.com/1",
        "https://b.com/1",
    ]


def test_diversify_jaccard_of_exactly_the_threshold_is_not_a_duplicate() -> None:
    """Strictly greater than: 4 shared of 5 = 0.8 exactly stays in the window."""
    fused = [
        _fr("https://a.com/1", "alpha beta gamma delta epsilon"),
        _fr("https://b.com/1", "alpha beta gamma delta"),
    ]
    assert [r.url for r in diversify(fused)] == ["https://a.com/1", "https://b.com/1"]
    # ...and one more shared token (5 of 6 = 0.833) tips it over
    fused[1] = _fr("https://b.com/1", "alpha beta gamma delta epsilon zeta")
    out = diversify(fused + [_fr("https://c.com/1", "unrelated")])
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://c.com/1",
        "https://b.com/1",
    ]


def test_diversify_empty_title_and_snippet_are_never_duplicates() -> None:
    fused = [_fr("https://a.com/1"), _fr("https://b.com/1"), _fr("https://c.com/1")]
    assert [r.url for r in diversify(fused)] == [r.url for r in fused]


def test_diversify_non_latin_text_yields_no_tokens_so_is_never_a_duplicate() -> None:
    """Documented limit of the [a-z0-9]+ tokenizer: pure CJK/Cyrillic text has no
    tokens, so near-dup demotion is a no-op for it (the host cap still applies)."""
    fused = [
        _fr("https://a.com/1", "квантовые вычисления"),
        _fr("https://b.com/1", "квантовые вычисления"),
    ]
    assert [r.url for r in diversify(fused)] == ["https://a.com/1", "https://b.com/1"]


def test_diversify_tokens_are_lowercased_alphanumeric_runs() -> None:
    """Case and punctuation are not signal: these two titles tokenize identically, so
    Jaccard is 1.0 and the later one is demoted below a third, unrelated host."""
    fused = [
        _fr("https://a.com/1", "Quantum-Computing: 2026!"),
        _fr("https://b.com/1", "quantum computing (2026)"),
        _fr("https://c.com/1", "other"),
    ]
    assert [r.url for r in diversify(fused)] == [
        "https://a.com/1",
        "https://c.com/1",
        "https://b.com/1",
    ]


def test_diversify_compares_against_every_kept_result_not_only_the_last() -> None:
    fused = [
        _fr("https://a.com/1", "alpha beta gamma delta epsilon"),
        _fr("https://b.com/1", "totally different words here"),
        _fr("https://c.com/1", "alpha beta gamma delta epsilon"),  # dup of #1, not #2
        _fr("https://d.com/1", "fresh"),
    ]
    out = diversify(fused)
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://b.com/1",
        "https://d.com/1",
        "https://c.com/1",
    ]


def test_diversify_a_demoted_result_does_not_count_toward_host_or_dups() -> None:
    """Only KEPT results define the window: a demoted near-dup neither uses up its
    host's quota nor becomes a comparison target for later candidates."""
    fused = [
        _fr("https://a.com/1", "alpha beta gamma delta epsilon"),
        # 5 of 6 shared with #1 -> demoted; must NOT count as b.com's first result
        _fr("https://b.com/1", "alpha beta gamma delta epsilon zeta"),
        _fr("https://b.com/2", "one"),
        _fr("https://b.com/3", "two"),  # b.com's SECOND kept result, so it fits
        # 5 of 6 shared with the DEMOTED #2 (dup if it were a target), only 4 of 6
        # with the kept #1 -> stays in the window
        _fr("https://c.com/1", "beta gamma delta epsilon zeta"),
    ]
    out = diversify(fused)
    assert [r.url for r in out] == [
        "https://a.com/1",
        "https://b.com/2",
        "https://b.com/3",
        "https://c.com/1",
        "https://b.com/1",
    ]


def test_diversify_none_disables_each_mechanism_independently() -> None:
    """Each mechanism leaves its own signature, so a None on either side is visible."""
    fused = [
        _fr("https://a.com/1", "alpha beta gamma delta epsilon"),
        _fr("https://a.com/2", "one"),
        _fr("https://a.com/3", "two"),  # third from a.com -> host cap demotes
        _fr("https://b.com/1", "alpha beta gamma delta epsilon zeta"),  # near-dup of #1
        _fr("https://c.com/1", "fresh"),
    ]
    a1, a2, a3, b1, c1 = (r.url for r in fused)
    assert [r.url for r in diversify(fused)] == [a1, a2, c1, a3, b1]
    assert [r.url for r in diversify(fused, max_per_host=None)] == [a1, a2, a3, c1, b1]
    assert [r.url for r in diversify(fused, near_dup_threshold=None)] == [
        a1,
        a2,
        b1,
        c1,
        a3,
    ]
    assert diversify(fused, max_per_host=None, near_dup_threshold=None) == fused


def test_diversify_window_zero_is_the_identity() -> None:
    fused = [_fr("https://a.com/1"), _fr("https://a.com/2"), _fr("https://a.com/3")]
    assert diversify(fused, max_per_host=1, window=0) == fused


def test_diversify_validates_its_parameters() -> None:
    with pytest.raises(ValueError, match="max_per_host must be >= 1"):
        diversify([], max_per_host=0)
    with pytest.raises(ValueError, match="near_dup_threshold must be within"):
        diversify([], near_dup_threshold=1.5)
    with pytest.raises(ValueError, match="near_dup_threshold must be within"):
        diversify([], near_dup_threshold=-0.1)
    with pytest.raises(ValueError, match="window must be >= 0"):
        diversify([], window=-1)


def test_diversify_boundary_parameter_values_are_accepted() -> None:
    fused = [
        _fr("https://a.com/1", "x y"),
        _fr("https://b.com/1", "x y z"),  # shares 2 of 3 tokens with #1
        _fr("https://c.com/1", "q"),
    ]
    # threshold 1.0 can never be exceeded -> near-dup effectively off
    assert diversify(fused, near_dup_threshold=1.0) == fused
    # threshold 0.0: any shared token at all is a duplicate
    assert [r.url for r in diversify(fused, near_dup_threshold=0.0)] == [
        "https://a.com/1",
        "https://c.com/1",
        "https://b.com/1",
    ]
    assert diversify(fused[:1], max_per_host=1) == fused[:1]


def test_diversify_is_pure_and_deterministic() -> None:
    fused = [_fr(f"https://a.com/{i}", f"t{i}") for i in range(5)]
    snapshot = list(fused)
    runs = [[r.url for r in diversify(fused)] for _ in range(3)]
    assert all(run == runs[0] for run in runs)
    assert fused == snapshot


def test_diversify_of_nothing_is_empty() -> None:
    assert diversify([]) == []


# --------------------------------------------------------------------------
# opt-in from the fusers — defaults preserve the pre-diversify behaviour
# --------------------------------------------------------------------------


def test_rrf_default_keyword_values_do_not_diversify() -> None:
    """Existing callers (query_plan, the hub) must see byte-identical behaviour."""
    fused = reciprocal_rank_fusion(
        {
            "exa": [
                "https://a.com/1",
                "https://a.com/2",
                "https://a.com/3",
                "https://b.com",
            ]
        }
    )
    assert [f.url for f in fused] == [
        "https://a.com/1",
        "https://a.com/2",
        "https://a.com/3",
        "https://b.com",
    ]


def test_rrf_opts_into_the_host_cap_by_keyword() -> None:
    fused = reciprocal_rank_fusion(
        {"exa": ["https://a.com/1", "https://a.com/2", "https://b.com"]}, max_per_host=1
    )
    assert [f.url for f in fused] == [
        "https://a.com/1",
        "https://b.com",
        "https://a.com/2",
    ]


def test_rrf_opts_into_near_dup_demotion_by_keyword() -> None:
    fused = reciprocal_rank_fusion(
        {
            "exa": [
                {"url": "https://a.com", "title": "alpha beta gamma delta epsilon"},
                {
                    "url": "https://b.com",
                    "title": "alpha beta gamma delta epsilon zeta",
                },
                {"url": "https://c.com", "title": "different"},
            ]
        },
        near_dup_threshold=0.8,
    )
    assert [f.url for f in fused] == ["https://a.com", "https://c.com", "https://b.com"]


def test_rrf_diversifies_before_applying_the_limit() -> None:
    """Otherwise a diverse result just past the cut could never be promoted into it."""
    fused = reciprocal_rank_fusion(
        {"exa": ["https://a.com/1", "https://a.com/2", "https://b.com"]},
        max_per_host=1,
        limit=2,
    )
    assert [f.url for f in fused] == ["https://a.com/1", "https://b.com"]


def test_rrf_honours_the_window_keyword() -> None:
    urls = ["https://a.com/1", "https://a.com/2", "https://a.com/3", "https://b.com"]
    # window of 2 fills before the cap can bite -> unchanged order
    fused = reciprocal_rank_fusion({"exa": urls}, max_per_host=2, window=2)
    assert [f.url for f in fused] == urls


def test_fuse_provider_payloads_passes_diversity_keywords_through() -> None:
    payloads = {
        "exa": {
            "results": [
                {"url": "https://a.com/1", "title": "alpha beta gamma delta epsilon"},
                {
                    "url": "https://a.com/2",
                    "title": "alpha beta gamma delta epsilon zeta",
                },
                {"url": "https://a.com/3", "title": "third from the same host"},
                {"url": "https://b.com", "title": "elsewhere"},
            ]
        }
    }
    plain = fuse_provider_payloads(payloads)
    assert [f.url for f in plain] == [
        "https://a.com/1",
        "https://a.com/2",
        "https://a.com/3",
        "https://b.com",
    ]
    diverse = fuse_provider_payloads(
        payloads, max_per_host=2, near_dup_threshold=0.8, window=10
    )
    assert [f.url for f in diverse] == [
        "https://a.com/1",
        "https://a.com/3",
        "https://b.com",
        "https://a.com/2",
    ]
