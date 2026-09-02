"""Tests for the capability index.

Every assertion here is POSITIVE ("exactly N of N", "this specific id resolves"), never
"nothing was wrong". The Wave-2 defect in this program was an aggregate reading
`0/0 conditions, 0 blocking` as PASS, so a test that can be satisfied by an empty walk is
not a test.
"""

from __future__ import annotations

import json

import pytest
from routing import index as ix

# --------------------------------------------------------------------------- fixtures


@pytest.fixture(scope="module")
def live():
    return ix.discover()


@pytest.fixture
def tiny(tmp_path):
    """A minimal fixture tree, injected through `Roots` -- the seam D3 had to add.

    Building this proves the walk is genuinely parameterized: if any source read a
    hardcoded path, the counts below would pick up the real 912-record inventory.
    """
    wf = tmp_path / "workflows"
    wf.mkdir()
    (wf / "alpha.json").write_text(
        json.dumps(
            {
                "id": "alpha-blueprint",
                "kind": "workflow",
                "name": "Alpha blueprint for widget calibration",
                "description": "Calibrate a widget using a torque wrench.",
                "tags": ["widget", "calibration"],
                "categories": ["engineering"],
                "flagship": True,
                "stages": [
                    {"id": "s1", "kind": "probe", "description": "measure torque"}
                ],
            }
        ),
        encoding="utf-8",
    )
    (wf / "meta.json").write_text(
        json.dumps(
            {"id": "meta-bp", "kind": "meta-workflow", "name": "A meta workflow"}
        ),
        encoding="utf-8",
    )
    (wf / "sub.json").write_text(
        json.dumps(
            {"id": "sub-bp", "kind": "subworkflow", "name": "A subworkflow fragment"}
        ),
        encoding="utf-8",
    )
    (wf / "REPORT-STATUS.json").write_text(
        json.dumps({"note": "not a blueprint"}), encoding="utf-8"
    )
    (wf / "nokind.json").write_text(
        json.dumps({"id": "x", "name": "no kind field"}), encoding="utf-8"
    )

    sk = tmp_path / "skills"
    (sk / "widgeter").mkdir(parents=True)
    (sk / "widgeter" / "SKILL.md").write_text(
        "---\nname: widgeter\ndescription: Use when calibrating widgets with a wrench. "
        "Do NOT use for sprockets.\n---\n\n# widgeter\n\n## Torque\nbody text here\n",
        encoding="utf-8",
    )
    return ix.Roots(workflows=wf, skills=[sk])


# --------------------------------------------------------------------------- injection seam


def test_roots_injection_is_a_real_seam(tiny):
    """The fixture tree -- and ONLY the fixture tree -- is discovered."""
    idx = ix.discover(tiny)
    assert idx.counts == {"skill": 1, "workflow": 3}, idx.counts
    assert sorted(r.id for r in idx.records) == [
        "skill:widgeter",
        "workflow:alpha-blueprint",
        "workflow:meta-bp",
        "workflow:sub-bp",
    ]


def test_all_three_workflow_kinds_are_indexed(tiny):
    """`kind == "workflow"` alone dropped 8 real blueprints from the live corpus."""
    kinds = {r.family for r in ix.discover(tiny).records if r.cls == "workflow"}
    assert kinds == {"blueprint-flagship", "blueprint-meta", "blueprint-sub"}, kinds


def test_status_sidecars_and_kindless_docs_are_excluded_by_shape(tiny):
    ids = {r.id for r in ix.discover(tiny).records}
    assert "workflow:x" not in ids, (
        "a doc with no `kind` must not be indexed as a blueprint"
    )
    assert not any("STATUS" in i.upper() for i in ids)


# --------------------------------------------------------------------------- fail-closed


def test_verify_floors_FIRES_on_a_deficient_index(tiny):
    """BOTH-STATES: the floor gate must go RED on a known-short index...

    This is the direction that matters. The gate caught a real defect during development
    (`workflow: 89 < floor 97`); a gate that has never gone red is indistinguishable from
    a no-op.
    """
    idx = ix.discover(tiny)
    violations = idx.verify_floors()
    assert violations, "floors must FIRE on a 4-record fixture index"
    assert any(v.startswith("skill:") for v in violations)


def test_verify_floors_PASSES_on_the_live_index(live):
    """...and GREEN on the real one. Silent in both states would measure nothing."""
    assert live.verify_floors() == [], live.verify_floors()


def test_main_returns_nonzero_when_floors_are_violated(monkeypatch, tiny):
    monkeypatch.setattr(ix.Roots, "live", classmethod(lambda cls: tiny))
    assert ix.main(["--json"]) == 1


def test_main_returns_zero_on_the_live_inventory():
    assert ix.main([]) == 0


# --------------------------------------------------------------------------- card cap


def test_every_card_is_within_the_byte_cap(live):
    """POSITIVE form: N of N, not 'none exceeded'."""
    n = len(live.records)
    within = sum(1 for r in live.records if r.card_bytes <= ix.CARD_BYTE_CAP)
    assert within == n, f"{n - within} of {n} cards exceed {ix.CARD_BYTE_CAP} B"
    assert n > 800, f"corpus implausibly small ({n}); the walk is probably broken"


def test_card_truncation_reserves_the_ellipsis_bytes():
    """The measured off-by-three: cap 220 produced a 221-byte card."""
    card, nb = ix.make_card("/x", "word " * 400)
    assert nb <= ix.CARD_BYTE_CAP
    assert card.endswith(ix.ELLIPSIS)


def test_card_truncation_never_splits_a_codepoint():
    for n in range(1, 40):
        card, nb = ix.make_card("/x", "éèê" * n + " tail")
        assert nb <= ix.CARD_BYTE_CAP
        card.encode("utf-8").decode("utf-8")  # would raise on a split codepoint


def test_card_is_far_cheaper_than_the_routing_text_it_projects(live):
    """The anti-flooding premise, asserted rather than assumed."""
    total_card = sum(r.card_bytes for r in live.records)
    total_routing = sum(len(r.routing_text.encode("utf-8")) for r in live.records)
    assert total_routing > total_card * 4, (total_routing, total_card)


# --------------------------------------------------------------------------- mining


def test_trigger_mining_finds_a_declared_trigger(tiny):
    rec = ix.discover(tiny).by_id()["skill:widgeter"]
    assert rec.triggers, "a 'Use when ...' sentence must yield a trigger"
    assert "calibrating widgets" in rec.triggers[0]


def test_anti_trigger_mining_finds_the_negative_scope(tiny):
    rec = ix.discover(tiny).by_id()["skill:widgeter"]
    assert any("sprocket" in a.lower() for a in rec.anti_triggers), rec.anti_triggers


def test_a_negated_clause_is_NOT_mined_as_a_positive_trigger():
    """MEASURED DEFECT: 'Do NOT use for ordinary code-quality review (use code-review)'
    was mined as a POSITIVE trigger, inverting the author's stated scope."""
    text = "Acceptance review of a finished change. Do NOT use for ordinary code-quality review."
    assert ix.mine_triggers(text) == (), ix.mine_triggers(text)
    assert ix.mine_anti_triggers(text), "the same sentence MUST yield an anti-trigger"


def test_mining_polarity_both_states():
    """Control: the identical sentence WITHOUT the negation does yield a trigger."""
    assert ix.mine_triggers("Use for ordinary code-quality review of a diff.")


# --------------------------------------------------------------------------- equivalence


def test_mirror_duplicates_are_grouped_on_the_live_inventory(live):
    groups = live.equivalence_groups()
    assert groups, (
        "the live trees mirror commands into the skill vault; groups must exist"
    )
    assert all(len(v) >= 2 for v in groups.values())
    assert "command:aside" in groups.get("command:aside", []), groups.get(
        "command:aside"
    )


def test_equivalence_requires_content_similarity_not_just_the_name(tmp_path):
    """A mirror whose content has DIVERGED must stop being grouped, not be suppressed."""
    sk = tmp_path / "skills"
    (sk / "source-command-thing").mkdir(parents=True)
    (sk / "source-command-thing" / "SKILL.md").write_text(
        "---\nname: source-command-thing\ndescription: Totally unrelated aardvark taxonomy.\n---\n",
        encoding="utf-8",
    )
    cmds = tmp_path / "commands"
    cmds.mkdir()
    (cmds / "thing.md").write_text(
        "---\nname: thing\ndescription: Calibrate a widget with a torque wrench.\n---\n",
        encoding="utf-8",
    )
    idx = ix.discover(ix.Roots(skills=[sk], commands=cmds))
    assert idx.equivalence_groups() == {}, "divergent content must NOT be grouped"


def test_cross_class_same_name_records_are_NOT_grouped(live):
    """`mcp:figma` / `skill:figma` / `plugin:figma` are related, not interchangeable."""
    by_id = live.by_id()
    figma = [i for i in by_id if i.endswith(":figma")]
    assert len(figma) >= 2, figma
    keys = {by_id[i].equiv_key for i in figma}
    assert keys == {""}, f"cross-class same-name must stay ungrouped, got {keys}"


# --------------------------------------------------------------------------- misc


def test_flatten_survives_every_shape_the_registry_actually_holds():
    """`tools` is a list in some candidate rows and a dict in others (measured KeyError)."""
    assert ix.flatten(["a", "b"]) == "a b"
    assert "k" in ix.flatten({"k": ["v"]})
    assert ix.flatten(None) == ""
    assert ix.flatten(7) == "7"
    assert ix.flatten({"a": {"b": ["c"]}}).count("c") == 1


def test_discovery_order_is_deterministic():
    a = [r.id for r in ix.discover().records]
    b = [r.id for r in ix.discover().records]
    assert a == b, "a nondeterministic walk makes every downstream tie-break unstable"


def test_ids_are_unique(live):
    ids = [r.id for r in live.records]
    assert len(ids) == len(set(ids)), "duplicate ids would double-count in every metric"


def test_every_record_has_a_resolvable_anchor(live):
    """A record whose anchor does not exist is a fabrication, not an index entry."""
    from pathlib import Path

    missing = [r.id for r in live.records if not Path(r.anchor).exists()]
    assert missing == [], f"records with unresolvable anchors: {missing[:5]}"
