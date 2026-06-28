"""Routing table + classifier tests (pure logic, no network)."""

from research_harness import routing
from research_harness.routing import (
    classify_capability,
    is_excluded,
    resolve_providers,
    route_subquestion,
)


def test_classifier_picks_capability_per_keyword():
    assert classify_capability("What papers study fusion confinement?") == "academic"
    assert classify_capability("Which gene drives this protein pathway?") == "bio"
    assert classify_capability("Show me a GitHub repo implementing raft") == "code"
    assert classify_capability("How to use the requests SDK api docs") == "library_docs"
    assert classify_capability("find similar via semantic search") == "neural"


def test_classifier_defaults_to_web():
    assert classify_capability("current state of the housing market") == "web"


def test_web_routes_firecrawl_primary_then_fallbacks():
    providers = resolve_providers("web")
    keys = [p.key for p in providers]
    assert keys[0] == "firecrawl.firecrawl_search"
    assert "exa.web_search_exa" in keys
    assert "tavily.tavily_search" in keys


def test_capability_primaries_match_policy():
    assert resolve_providers("neural")[0].key == "exa.web_search_exa"
    assert resolve_providers("academic")[0].server == "scholarly-access"
    assert resolve_providers("bio")[0].server == "tooluniverse"
    assert resolve_providers("library_docs")[0].server == "context7"
    assert resolve_providers("code")[0].server == "exa"
    assert resolve_providers("deep_read")[0].key == "firecrawl.firecrawl_scrape"


def test_unknown_capability_falls_back_to_web():
    assert resolve_providers("nonsense")[0].key == resolve_providers("web")[0].key


def test_live_filter_drops_down_servers_and_keeps_order():
    # firecrawl down -> exa becomes the live primary for web.
    providers = resolve_providers("web", live_servers={"exa", "tavily"})
    keys = [p.key for p in providers]
    assert keys == ["exa.web_search_exa", "tavily.tavily_search"]


def test_top_n_caps_for_corroboration_diversity():
    providers = resolve_providers("web", top_n=2)
    assert len(providers) == 2


def test_sci_hub_and_regressed_tool_are_excluded():
    sci_hub = routing.Provider("sci-hub", "fetch", routing.TIER_C)
    regressed = routing.Provider("scholarly-access", "paper_find_oa_pdf", routing.TIER_A)
    assert is_excluded(sci_hub)
    assert is_excluded(regressed)


def test_parked_servers_excluded():
    assert is_excluded(routing.Provider("scrapegraph", "scrape", routing.TIER_B))
    assert is_excluded(routing.Provider("apify", "run", routing.TIER_B))


def test_route_subquestion_combines_classify_and_resolve():
    capability, providers = route_subquestion(
        "Which clinical trial measured this drug?",
        live_servers={"tooluniverse", "scholarly-access"},
    )
    assert capability == "bio"
    assert providers[0].server == "tooluniverse"


def test_excluded_tool_never_appears_in_resolved_lists():
    for capability in routing.ROUTING_TABLE:
        for provider in resolve_providers(capability):
            assert not is_excluded(provider)
