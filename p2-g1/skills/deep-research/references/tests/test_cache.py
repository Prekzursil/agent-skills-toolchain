"""Query-hash cache tests: key stability, hit/miss, TTL expiry, corruption."""

from research_harness.cache import (
    DEFAULT_TTL,
    fetch_with_cache,
    normalize_query,
    query_hash,
    read_cache,
    ttl_for,
    write_cache,
    ResearchCacheEntry,
)


def test_query_hash_is_stable_under_normalization():
    a = query_hash(
        "web", "firecrawl.firecrawl_search", "  Fusion  Energy ", {"limit": 8}
    )
    b = query_hash("web", "firecrawl.firecrawl_search", "fusion energy", {"limit": 8})
    assert a == b
    assert len(a) == 64  # sha-256 hex


def test_query_hash_changes_with_provider_and_params():
    base = query_hash("web", "firecrawl.firecrawl_search", "q", {"limit": 8})
    other_provider = query_hash("web", "exa.web_search_exa", "q", {"limit": 8})
    other_params = query_hash("web", "firecrawl.firecrawl_search", "q", {"limit": 5})
    assert base != other_provider
    assert base != other_params


def test_normalize_query_collapses_whitespace_and_case():
    assert normalize_query("  A   B\tC ") == "a b c"


def test_write_then_read_is_a_hit(tmp_path):
    qhash = query_hash("web", "firecrawl.firecrawl_search", "q", None)
    entry = ResearchCacheEntry(
        query_hash=qhash,
        capability="web",
        provider="firecrawl.firecrawl_search",
        fetched_at=1000.0,
        payload={"results": [1, 2, 3]},
    )
    write_cache(tmp_path, entry)
    got = read_cache(tmp_path, qhash, ttl=DEFAULT_TTL, now=1000.0)
    assert got is not None
    assert got.payload == {"results": [1, 2, 3]}


def test_missing_entry_is_a_miss(tmp_path):
    assert read_cache(tmp_path, "deadbeef", ttl=DEFAULT_TTL, now=0.0) is None


def test_expired_entry_is_a_miss(tmp_path):
    qhash = "abc123"
    entry = ResearchCacheEntry(
        query_hash=qhash,
        capability="web",
        provider="firecrawl.firecrawl_search",
        fetched_at=0.0,
        payload={"x": 1},
    )
    write_cache(tmp_path, entry)
    # now well past the 24h web TTL -> miss
    assert (
        read_cache(tmp_path, qhash, ttl=ttl_for("web"), now=ttl_for("web") + 1) is None
    )
    # still inside TTL -> hit
    assert read_cache(tmp_path, qhash, ttl=ttl_for("web"), now=10.0) is not None


def test_corrupt_entry_is_a_miss(tmp_path):
    (tmp_path / "corrupt.json").write_text("{not valid json", encoding="utf-8")
    assert read_cache(tmp_path, "corrupt", ttl=DEFAULT_TTL, now=0.0) is None


def test_ttl_for_capability_lookup():
    assert ttl_for("academic") > ttl_for("web")
    assert ttl_for("unknown-capability") == DEFAULT_TTL


def test_fetch_with_cache_miss_then_hit(tmp_path):
    calls = {"n": 0}

    def fake_provider():
        calls["n"] += 1
        return {"data": "fresh"}

    first = fetch_with_cache(
        "academic",
        "scholarly-access.paper_resolve",
        "crispr review",
        fake_provider,
        cache_dir=tmp_path,
        now=500.0,
    )
    assert first.hit is False
    assert calls["n"] == 1

    second = fetch_with_cache(
        "academic",
        "scholarly-access.paper_resolve",
        "CRISPR review",  # different case -> same normalized key
        fake_provider,
        cache_dir=tmp_path,
        now=600.0,
    )
    assert second.hit is True
    assert second.payload == {"data": "fresh"}
    assert calls["n"] == 1  # provider not called again


def test_no_cache_flag_always_calls_provider(tmp_path):
    calls = {"n": 0}

    def fake_provider():
        calls["n"] += 1
        return {"data": calls["n"]}

    for _ in range(3):
        result = fetch_with_cache(
            "web",
            "firecrawl.firecrawl_search",
            "q",
            fake_provider,
            cache_enabled=False,
            cache_dir=tmp_path,
            now=1.0,
        )
        assert result.hit is False
    assert calls["n"] == 3
