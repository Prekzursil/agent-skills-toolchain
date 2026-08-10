"""Tests for description scoring and structural enrichment.

The headline finding this file pins is the ZERO-TRIGGER result on the PLATFORM-AUTHORED
inventory: 454 records across workflow/protocol/preset/candidate/command declare no trigger
prose at all. That is the concrete answer to the spec's "improve descriptions for routing",
so it is asserted rather than left in prose where it can silently stop being true.

(The assertion originally also covered `plugin` and `mcp` and FIRED when this unit started
reading their real vendor manifests -- one of 98 plugin descriptions does say "Use when".
The scope was narrowed to what this program authors and can act on, rather than the code
being changed back to make the test pass. See the SCOPE NOTE in the test.)
"""

from __future__ import annotations

import pytest
from routing import descriptions as ds
from routing.index import KIND_FAMILY, discover


@pytest.fixture(scope="module")
def live():
    return discover()


@pytest.fixture(scope="module")
def stats(live):
    return ds.corpus_stats(live)


def test_tokens_drops_stopwords_and_keeps_domain_terms():
    t = ds.tokens("Use this when you need to reframe a video to vertical")
    assert "reframe" in t and "vertical" in t and "video" in t
    for stop in ("use", "this", "when", "you", "need", "to"):
        assert stop not in t, stop


def test_corpus_stats_reports_a_real_length_distribution(stats):
    assert stats["n"] > 800
    assert 0 < stats["median_chars"] < stats["p90_chars"] <= stats["max_chars"]


def test_score_rewards_a_trigger_and_an_anti_trigger(live, stats):
    """A description that says WHEN and WHEN NOT must outscore one that says neither."""
    from routing.index import Capability

    def mk(desc, triggers=(), anti=()):
        c = Capability(
            id="skill:x",
            cls="skill",
            name="x",
            anchor=__file__,
            routing_text=desc,
            card="c",
            card_bytes=1,
            desc_source=desc,
            triggers=triggers,
            anti_triggers=anti,
        )
        return ds.score(c, stats)

    bare = mk("A thing that does stuff with files and code.")
    full = mk(
        "Reframe horizontal footage to a 9:16 vertical crop with subject tracking.",
        triggers=("converting a landscape clip to vertical",),
        anti=("static image resizing",),
    )
    assert full.total > bare.total, (full.total, bare.total)
    assert "trigger" in bare.missing and "anti_trigger" in bare.missing
    assert full.has_trigger and full.has_anti_trigger


def test_report_ranks_the_worst_descriptions_first(live):
    rep = ds.report(live, limit=10)
    scores = [w["score"] for w in rep["worst"]]
    assert scores == sorted(scores), scores
    assert rep["corpus"]["n"] == len(live.records)
    assert rep["missing_field_counts"]


def test_the_platform_authored_inventory_declares_NO_trigger_prose(live):
    """MEASURED headline: trigger prose ("Use when ...", "Triggers include ...") exists for
    251/328 skills and 4/18 agents, and for ZERO of the 454 PLATFORM-AUTHORED records.

    This is the most actionable description-quality finding in the unit: those records are
    reachable only through descriptions written as titles and objectives, with no authored
    statement of WHEN to use them.
    """
    # SCOPE NOTE -- this assertion was NARROWED after it fired. `plugin` and `mcp` are
    # THIRD-PARTY-described: their text comes from vendor manifests and a curated hints
    # map, not from this program, and 1/98 plugin manifests does carry "Use when" prose.
    # Asserting 0 there was asserting something about other people's writing. The claim
    # that matters, and that this program can act on, is about the records the platform
    # authors ITSELF: 102 workflows, 48 protocols, 69 presets, 164 candidates, 71 commands.
    for cls in ("workflow", "protocol", "preset", "candidate", "command"):
        recs = live.by_class(cls)
        assert recs, cls
        with_trig = sum(1 for r in recs if r.triggers)
        assert with_trig == 0, f"{cls}: {with_trig}/{len(recs)} now declare triggers"
    skills = live.by_class("skill")
    assert sum(1 for r in skills if r.triggers) > 200, (
        "skills DO declare triggers (control)"
    )


def test_third_party_described_classes_are_reported_not_asserted(live):
    """`plugin`/`mcp` text is vendor-authored, so only its PRESENCE is a fair assertion.

    Both were measured as routing-dead before this unit read their real sources: 98/98
    plugins carried a synthesized "Installed plugin X from marketplace Y" and 9/14 MCP
    servers had no domain vocabulary at all.
    """
    for cls in ("plugin", "mcp"):
        recs = live.by_class(cls)
        assert recs, cls
        described = sum(1 for r in recs if len(r.desc_source) > 40)
        assert described >= len(recs) * 0.7, (
            f"{cls}: only {described}/{len(recs)} described"
        )


def test_mcp_records_carry_real_domain_vocabulary(live):
    """Before the curated hints were reused, an mcp record's whole routing text was
    "MCP server <name> tool family" and the breadth probe selected 0 of 14 servers."""
    mcps = live.by_class("mcp")
    assert len(mcps) >= 10
    enriched = [r for r in mcps if len(r.desc_source) > 60]
    assert len(enriched) >= 8, [r.name for r in mcps if len(r.desc_source) <= 60]


def test_enrich_is_idempotent(live):
    """A second pass must not re-append: duplicated aliases would skew every corpus IDF."""
    import copy

    idx = copy.deepcopy(live)
    ds.enrich(idx)
    once = {r.id: r.routing_text for r in idx.records}
    second = ds.enrich(idx)
    assert second == 0, f"{second} records re-enriched on the second pass"
    assert {r.id: r.routing_text for r in idx.records} == once


def test_enrich_actually_changes_the_corpus(live):
    """BOTH-STATES: a no-op enrichment would make its ablation arm meaningless."""
    import copy

    idx = copy.deepcopy(live)
    before = {r.id: r.routing_text for r in idx.records}
    n = ds.enrich(idx)
    changed = sum(1 for r in idx.records if r.routing_text != before[r.id])
    assert n == changed and changed > 100, (n, changed)


def test_every_kind_family_has_a_structural_alias():
    """Keeps `index.KIND_FAMILY` and `descriptions.STRUCTURAL_ALIASES` in step. The
    `blueprint-subsub` bug silently broke exactly this lookup."""
    for kind, family in KIND_FAMILY.items():
        assert family in ds.STRUCTURAL_ALIASES, f"{kind} -> {family} has no alias"


def test_every_family_the_index_emits_is_known_to_the_aliases(live):
    emitted = {r.family for r in live.records if r.family and r.cls == "workflow"}
    unknown = emitted - set(ds.STRUCTURAL_ALIASES)
    assert unknown == set(), unknown
