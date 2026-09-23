"""Keep SKILL.md synchronized with executable routing and module references."""

from pathlib import Path

from research_harness.budget import EFFORT_CALLS
from research_harness.preflight import NO_RETRY_SERVERS
from research_harness.report import REPORT_STATUSES
from research_harness.routing import (
    ASYNC_COMPANIONS,
    CAPABILITY_FALLBACKS,
    METERED_TOOLS,
    ROUTING_TABLE,
    all_provider_specs,
)

SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL = SKILL_ROOT / "SKILL.md"

# Lens 3's borrow order; the prose subsections must appear in this sequence.
LENS3_BORROW_ORDER = (
    "Budget + beast mode",
    "Evolving report",
    "Snippet windows + Wayback fallback",
    "Academic route",
    "Contracts",
    "Perspectives",
    "Learnings",
    "DAG",
    "Curation",
)
# Lens 12 prose-only items (finds 10-12) that ride along in the same section.
LENS12_PROSE_ITEMS = ("Hedge filter", "CoVe", "Volatility")


def test_skill_names_every_routed_exact_tool():
    text = SKILL.read_text(encoding="utf-8")
    for provider in all_provider_specs():
        assert f"`{provider.tool}`" in text, provider.key


def test_skill_does_not_reintroduce_known_stale_tool_names():
    text = SKILL.read_text(encoding="utf-8")
    for stale in (
        "`query_docs`",
        "`cve_lookup`",
        "`cve_search`",
        "`cve_kev_list`",
        "`huggingface.paper_search`",
    ):
        assert stale not in text


def test_every_documented_harness_module_exists():
    text = SKILL.read_text(encoding="utf-8")
    harness = SKILL_ROOT / "references" / "research_harness"
    for module in (
        "routing.py",
        "preflight.py",
        "harness.py",
        "cache.py",
        "academic.py",
        "claims.py",
        "grading.py",
        "calibration.py",
        "report.py",
        # Reliability set (Lens 12).
        "budget.py",
        "checkpoint.py",
        "loopguard.py",
        "compact.py",
        "sufficiency.py",
        "conflicts.py",
    ):
        assert f"`{module}`" in text
        assert (harness / module).is_file()


def test_skill_routing_table_rows_match_the_code_table():
    """Each capability row in SKILL.md is generated from ``ROUTING_TABLE`` verbatim."""
    text = SKILL.read_text(encoding="utf-8")
    for capability, providers in ROUTING_TABLE.items():
        chain = " -> ".join(p.label for p in providers)
        assert f"| `{capability}` | {chain} |" in text, capability
    for capability, fallbacks in CAPABILITY_FALLBACKS.items():
        assert f"`{capability}`" in text
        for fallback in fallbacks:
            assert f"`{fallback}`" in text


def test_skill_documents_every_terminal_status_and_effort_class():
    text = SKILL.read_text(encoding="utf-8")
    for status in REPORT_STATUSES:
        assert f"`{status}`" in text, status
    for effort, calls in EFFORT_CALLS.items():
        assert f"`{effort}`" in text, effort
    assert "3 / 8 / 15" in text


def test_skill_documents_metered_tools_and_async_companions():
    text = SKILL.read_text(encoding="utf-8")
    for tool in METERED_TOOLS:
        assert f"`{tool}`" in text, tool
    for companions in ASYNC_COMPANIONS.values():
        for tool in companions:
            assert f"`{tool}`" in text, tool
    # Metered lanes are budget-gated to the explore regime.
    assert "explore" in text and "metered" in text.lower()


def test_skill_records_the_perplexity_no_retry_rule_and_owner_action():
    text = SKILL.read_text(encoding="utf-8")
    for server in NO_RETRY_SERVERS:
        assert server in text
    assert "never retried" in text
    assert "OWNER-ACTION" in text
    assert "`PERPLEXITY_SESSION_TOKEN`" in text
    assert "`.agents/local.json`" in text


def test_skill_documents_the_academic_searxng_lane_caveats():
    text = SKILL.read_text(encoding="utf-8")
    assert "categories=science" in text
    assert "`searxng_instance_info`" in text
    assert "time_range" in text


def test_prose_borrows_follow_lens3_order_and_include_lens12_items():
    text = SKILL.read_text(encoding="utf-8")
    positions = [text.index(f"### {heading}") for heading in LENS3_BORROW_ORDER]
    assert positions == sorted(positions), LENS3_BORROW_ORDER
    for item in LENS12_PROSE_ITEMS:
        assert f"### {item}" in text, item
    # Every subsection says when to use it.
    borrows_start = positions[0]
    expected_subsections = len(LENS3_BORROW_ORDER) + len(LENS12_PROSE_ITEMS)
    assert text.count("**When to use:**", borrows_start) >= expected_subsections
