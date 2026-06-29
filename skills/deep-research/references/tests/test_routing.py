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


def test_classifier_routes_explain_compare_consensus_to_synthesis():
    assert classify_capability("Compare React and Vue performance") == "synthesis"
    assert classify_capability("Explain how diffusion models work") == "synthesis"
    assert classify_capability("What is the consensus on intermittent fasting?") == "synthesis"
    # NB: avoid substrings of domain keywords here (e.g. "monorepos" contains
    # "repo" -> the earlier `code` rule wins); that ordering is intentional.
    assert classify_capability("pros and cons of microservices") == "synthesis"


def test_domain_keywords_win_over_synthesis_phrasing():
    # A domain-specific question phrased as "compare/explain" still routes to its
    # domain (synthesis is the LAST rule), so raw academic/bio work is unaffected.
    assert classify_capability("Compare two peer-reviewed papers on this drug") == "bio"
    assert classify_capability("Explain the arxiv preprint's methodology") == "academic"


def test_classifier_defaults_to_web():
    assert classify_capability("current state of the housing market") == "web"


def test_web_routes_firecrawl_primary_then_perplexity_then_fallbacks():
    providers = resolve_providers("web")
    keys = [p.key for p in providers]
    # Raw-extraction primary stays firecrawl; Perplexity is the high-priority
    # cited corroborator at #2, ahead of exa/tavily.
    assert keys[0] == "firecrawl.firecrawl_search"
    assert keys[1] == "perplexity.pplx_smart_query"
    assert "exa.web_search_exa" in keys
    assert "tavily.tavily_search" in keys


def test_synthesis_routes_perplexity_primary_then_raw_fallbacks():
    providers = resolve_providers("synthesis")
    keys = [p.key for p in providers]
    assert keys[0] == "perplexity.pplx_smart_query"
    assert keys[1:] == ["exa.web_search_exa", "firecrawl.firecrawl_search"]


def test_capability_primaries_match_policy():
    assert resolve_providers("synthesis")[0].server == "perplexity"
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
    # The top-2 web corroboration pair is now firecrawl (raw) + Perplexity (cited).
    assert [p.key for p in providers] == [
        "firecrawl.firecrawl_search",
        "perplexity.pplx_smart_query",
    ]


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


# --- New key-free providers: SearXNG + cve-mcp (M-16c) ---------------------


def test_classifier_routes_vuln_keywords():
    assert classify_capability("Lookup CVE-2024-3094 details") == "vuln"
    assert classify_capability("Is there a known exploit for this library?") == "vuln"
    assert classify_capability("What is the CVSS score of log4shell?") == "vuln"
    assert classify_capability("Is there an RCE exploit for this?") == "vuln"
    assert classify_capability("Is this in the CISA KEV catalog?") == "vuln"
    assert classify_capability("Any zero-day or 0-day for this product?") == "vuln"


def test_classifier_vuln_tokens_guarded_against_false_positives():
    # Bare "rce"/"kev" substrings must NOT false-match these non-security words.
    assert classify_capability("Show me the source code for raft") == "code"
    assert classify_capability("How to manage a shared resource pool") != "vuln"
    assert classify_capability("Who is Kevin and what did he build?") != "vuln"


def test_vuln_capability_routes_cve_mcp_in_order():
    providers = resolve_providers("vuln")
    keys = [p.key for p in providers]
    assert keys == [
        "cve-mcp.cve_lookup",
        "cve-mcp.cve_search",
        "cve-mcp.cve_kev_list",
    ]
    assert all(p.server == "cve-mcp" for p in providers)
    # cve-mcp carries an authoritative (A) source-tier prior.
    assert providers[0].source_tier == routing.TIER_A


def test_web_inserts_searxng_keyfree_corroborator_ahead_of_keyed():
    keys = [p.key for p in resolve_providers("web")]
    # firecrawl raw -> perplexity cited -> searxng KEY-FREE -> exa -> tavily.
    assert keys[0] == "firecrawl.firecrawl_search"
    assert keys[1] == "perplexity.pplx_smart_query"
    assert keys[2] == "searxng.searxng_web_search"
    # SearXNG sits ahead of the keyed exa/tavily corroborators.
    assert keys.index("searxng.searxng_web_search") < keys.index("exa.web_search_exa")
    assert keys.index("searxng.searxng_web_search") < keys.index("tavily.tavily_search")


def test_classifier_routes_longtail_to_searxng():
    assert classify_capability("Find obscure forum mentions of this part number") == "longtail"
    assert classify_capability("A rarely documented config flag for this tool") == "longtail"
    providers = resolve_providers("longtail")
    assert providers[0].key == "searxng.searxng_web_search"
    assert providers[0].source_tier == routing.TIER_B
    # exa is the neural fallback for long-tail.
    assert providers[-1].server == "exa"


def test_vuln_live_filter_degrades_gracefully():
    # cve-mcp down -> vuln resolves to no providers (caller falls back to web).
    assert resolve_providers("vuln", live_servers={"firecrawl"}) == []
    assert resolve_providers("vuln", live_servers={"cve-mcp"})[0].server == "cve-mcp"
