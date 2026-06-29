"""Preflight + harness-plan integration tests (pure, injected probe)."""

from research_harness.harness import plan_research
from research_harness.preflight import (
    DOWN,
    LIVE,
    QUOTA,
    down_servers,
    live_servers,
    routable_servers,
    run_preflight,
)


def test_routable_servers_excludes_guardrailed_and_parked():
    servers = routable_servers()
    assert "firecrawl" in servers
    assert "scholarly-access" in servers
    assert "perplexity" in servers  # cookie/session-auth synthesis provider
    assert "sci-hub" not in servers
    assert "scrapegraph" not in servers
    assert "apify" not in servers


def test_run_preflight_classifies_states():
    def probe(server):
        return {"firecrawl": LIVE, "exa": DOWN, "tavily": QUOTA}.get(server, LIVE)

    statuses = run_preflight(probe, servers={"firecrawl", "exa", "tavily"})
    assert statuses["firecrawl"].state == LIVE
    assert statuses["exa"].state == DOWN
    assert statuses["tavily"].state == QUOTA
    assert live_servers(statuses) == {"firecrawl"}
    assert down_servers(statuses) == ["exa", "tavily"]


def test_probe_exception_is_treated_as_down():
    def probe(server):
        raise RuntimeError("boom")

    statuses = run_preflight(probe, servers={"firecrawl"})
    assert statuses["firecrawl"].state == DOWN


def test_invalid_probe_value_is_treated_as_down():
    statuses = run_preflight(lambda s: "weird", servers={"firecrawl"})
    assert statuses["firecrawl"].state == DOWN


def test_plan_research_routes_around_down_primary():
    # firecrawl down -> web sub-question falls to Perplexity (the high-priority
    # #2 web provider) as the live primary, then exa.
    def probe(server):
        return DOWN if server == "firecrawl" else LIVE

    statuses = run_preflight(probe)
    plan = plan_research(
        ["current state of the housing market", "recent papers on quantum error correction"],
        statuses,
        top_n=2,
    )
    web_decision = plan.decisions[0]
    assert web_decision.capability == "web"
    assert web_decision.providers[0].server == "perplexity"
    assert web_decision.providers[1].server == "exa"
    assert "firecrawl" in plan.providers_down

    academic_decision = plan.decisions[1]
    assert academic_decision.capability == "academic"
    assert academic_decision.providers[0].server == "scholarly-access"


def test_plan_research_routes_synthesis_question_to_perplexity():
    # "explain/compare" sub-question routes to the synthesis capability with
    # Perplexity as the live primary.
    statuses = run_preflight(lambda s: LIVE)
    plan = plan_research(["compare Rust and Go for systems programming"], statuses, top_n=2)
    decision = plan.decisions[0]
    assert decision.capability == "synthesis"
    assert decision.providers[0].server == "perplexity"


def test_plan_research_top_n_limits_providers():
    statuses = run_preflight(lambda s: LIVE)
    plan = plan_research(["general web question"], statuses, top_n=1)
    assert len(plan.decisions[0].providers) == 1


def test_routed_provider_keys_are_distinct_and_ordered():
    statuses = run_preflight(lambda s: LIVE)
    plan = plan_research(["web q one", "web q two"], statuses, top_n=2)
    keys = plan.routed_provider_keys
    assert len(keys) == len(set(keys))
    assert keys[0] == "firecrawl.firecrawl_search"
