"""Preflight + harness-plan integration tests (pure, injected probe)."""

import pytest

from research_harness.budget import EFFORT_CALLS
from research_harness.harness import classify_effort, plan_research
from research_harness.preflight import (
    DOWN,
    LIVE,
    NO_RETRY_SERVERS,
    QUOTA,
    ProviderStatus,
    down_servers,
    live_servers,
    retry_allowed,
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
    # #2 web provider) as the live primary, then SearXNG (the key-free #3
    # corroborator, now ahead of the keyed exa/tavily).
    def probe(server):
        return DOWN if server == "firecrawl" else LIVE

    statuses = run_preflight(probe)
    plan = plan_research(
        [
            "current state of the housing market",
            "recent papers on quantum error correction",
        ],
        statuses,
        top_n=2,
    )
    web_decision = plan.decisions[0]
    assert web_decision.capability == "web"
    assert web_decision.providers[0].server == "perplexity"
    assert web_decision.providers[1].server == "searxng"
    assert "firecrawl" in plan.providers_down

    academic_decision = plan.decisions[1]
    assert academic_decision.capability == "academic"
    assert academic_decision.providers[0].server == "scholarly-access"


def test_plan_research_routes_synthesis_question_to_perplexity():
    # "explain/compare" sub-question routes to the synthesis capability with
    # Perplexity as the live primary.
    statuses = run_preflight(lambda s: LIVE)
    plan = plan_research(
        ["compare Rust and Go for systems programming"], statuses, top_n=2
    )
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


# --- Sub-question DAG + effort classes (Lens 12 find 8) -----------------------


def test_decisions_default_to_input_order_with_fact_effort_and_indexes():
    statuses = run_preflight(lambda s: LIVE)
    plan = plan_research(["what is X", "who makes X"], statuses)
    assert [d.index for d in plan.decisions] == [0, 1]
    assert all(d.depends_on == () for d in plan.decisions)
    assert all(d.effort == "fact" for d in plan.decisions)
    assert all(d.call_allotment == EFFORT_CALLS["fact"] for d in plan.decisions)
    assert plan.total_allotment == 2 * EFFORT_CALLS["fact"]
    assert plan.skipped == ()


def test_dependencies_are_executed_in_topological_order():
    statuses = run_preflight(lambda s: LIVE)
    subqs = ["market size of X", "who are the leaders in X", "what is X"]
    # 0 depends on 2 and 1; 1 depends on 2 -> 2, 1, 0.
    plan = plan_research(subqs, statuses, depends_on={0: (2, 1), 1: (2,)})
    assert [d.index for d in plan.decisions] == [2, 1, 0]
    assert plan.decisions[2].depends_on == (2, 1)
    assert plan.decisions[0].subquestion == "what is X"


def test_dependency_cycle_is_rejected():
    statuses = run_preflight(lambda s: LIVE)
    with pytest.raises(ValueError, match="cycle"):
        plan_research(["a", "b"], statuses, depends_on={0: (1,), 1: (0,)})


def test_out_of_range_dependency_and_unknown_effort_are_rejected():
    statuses = run_preflight(lambda s: LIVE)
    with pytest.raises(ValueError, match="depends_on"):
        plan_research(["a"], statuses, depends_on={0: (3,)})
    with pytest.raises(ValueError, match="effort"):
        plan_research(["a"], statuses, efforts={0: "heroic"})


def test_effort_classes_drive_call_allotments():
    statuses = run_preflight(lambda s: LIVE)
    subqs = [
        "what year was Acme founded",
        "compare Rust and Go for backend services",
        "deep research: the full landscape of solid-state batteries",
    ]
    plan = plan_research(subqs, statuses)
    efforts = [d.effort for d in plan.decisions]
    assert efforts == ["fact", "compare", "deep"]
    assert [d.call_allotment for d in plan.decisions] == [3, 8, 15]
    assert plan.total_allotment == 26
    # An explicit override wins over the heuristic.
    forced = plan_research(subqs, statuses, efforts={0: "deep"})
    assert forced.decisions[0].effort == "deep"
    assert forced.decisions[0].call_allotment == 15


def test_classify_effort_heuristics():
    assert classify_effort("what is the population of France", "web") == "fact"
    assert classify_effort("pros and cons of microservices", "synthesis") == "compare"
    assert classify_effort("Rust vs Go", "web") == "compare"
    assert (
        classify_effort("comprehensive landscape of AI code editors", "web") == "deep"
    )
    assert classify_effort("anything", "deep_research") == "deep"
    assert classify_effort("anything", "council") == "deep"


def test_completed_subquestions_are_skipped_on_resume():
    statuses = run_preflight(lambda s: LIVE)
    subqs = ["what is X", "who makes X", "market size of X"]
    plan = plan_research(subqs, statuses, completed_subquestions=["What is X  "])
    assert plan.skipped == ("what is X",)
    assert [d.subquestion for d in plan.decisions] == [
        "who makes X",
        "market size of X",
    ]
    # Indexes still refer to the ORIGINAL plan positions so ledgers line up.
    assert [d.index for d in plan.decisions] == [1, 2]


def test_plan_uses_capability_fallback_and_records_it():
    live = {"scholarly-access", "searxng", "tavily"}
    statuses = {s: ProviderStatus(s, LIVE) for s in live}
    statuses["perplexity"] = ProviderStatus("perplexity", DOWN)
    plan = plan_research(["Deep research: the full landscape of X"], statuses)
    decision = plan.decisions[0]
    assert decision.capability == "deep_research"
    # tavily.tavily_research is on the deep_research chain and live -> no fallback.
    assert decision.fallback_capability is None
    assert decision.providers[0].key == "tavily.tavily_research"

    statuses.pop("tavily")
    plan = plan_research(["Deep research: the full landscape of X"], statuses)
    decision = plan.decisions[0]
    assert decision.fallback_capability == "academic"
    assert decision.providers[0].key == "scholarly-access.paper_resolve"


# --- Preflight no-retry rule (G-5b) ------------------------------------------


def test_perplexity_is_routed_around_never_retried_within_a_run():
    assert "perplexity" in NO_RETRY_SERVERS
    assert not retry_allowed(ProviderStatus("perplexity", DOWN))
    assert not retry_allowed(ProviderStatus("perplexity", QUOTA))
    assert retry_allowed(ProviderStatus("perplexity", LIVE))


def test_quota_exhaustion_is_never_retried_but_a_plain_down_may_be():
    assert not retry_allowed(ProviderStatus("exa", QUOTA))
    assert retry_allowed(ProviderStatus("exa", DOWN))
    assert retry_allowed(ProviderStatus("exa", LIVE))
