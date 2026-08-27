"""Keep SKILL.md synchronized with executable routing and module references."""

from pathlib import Path

from research_harness.routing import all_provider_specs


SKILL_ROOT = Path(__file__).resolve().parents[2]
SKILL = SKILL_ROOT / "SKILL.md"


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
    ):
        assert f"`{module}`" in text
        assert (harness / module).is_file()
