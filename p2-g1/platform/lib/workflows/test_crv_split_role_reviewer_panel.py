"""End-to-end test for FLAGSHIP blueprint BP-CRV-01 (card 49), crv.split-role-reviewer-panel.

Mechanism protected: recall comes from a DISJOINT ROLE PARTITION over one diff, with the author
excluded, and a silent reviewer treated as a suspect measurement rather than a clean result.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bp5_testkit as kit  # noqa: E402
from wfdsl import expr as _expr  # noqa: E402

SLUG = "crv.split-role-reviewer-panel"


def doc() -> dict:
    return kit.load(SLUG)


def test_validates_on_disk() -> None:
    kit.assert_accepted(doc())


def test_it_is_a_fanout_panel_and_deliberately_not_a_council() -> None:
    """The card's own non-duplicate argument. A council stage would mean rounds and consensus;
    this has neither, and encoding it as a council would collide with the D4-council family."""
    d = doc()
    kinds = {s["kind"] for s in d["stages"]}
    assert "fanout" in kinds
    assert "council" not in kinds, (
        "a panel with no deliberation must not be encoded as a council"
    )
    panel = next(s for s in d["stages"] if s["id"] == "review-panel")
    assert len(panel["over"]["items"]) >= 3, (
        "fewer than three roles is not a split-role panel"
    )
    assert panel["max_concurrency"] >= 3


def test_security_role_is_present_by_construction_not_by_hope() -> None:
    d = doc()
    assert "security-reviewer" in d["roles"]
    assert d["roles"]["security-reviewer"]["authority"] == "veto"
    assert (
        "SECURITY"
        in next(s for s in d["stages"] if s["id"] == "review-panel")["over"]["items"]
    )


def test_reviewers_are_independent_and_the_reconciler_authors_nothing() -> None:
    """AGENTS.md 5: an independent role must not receive a sibling's raw output as prefix context."""
    d = doc()
    for name in (
        "senior-reviewer",
        "security-reviewer",
        "consistency-reviewer",
        "cross-vendor-reviewer",
    ):
        assert d["roles"][name]["independence"] == "independent", (
            f"{name} is not independent"
        )
    assert d["roles"]["cross-vendor-reviewer"]["cross_vendor_required"] is True
    assert d["roles"]["cross-vendor-reviewer"]["vendor"] == "openai"
    assert d["roles"]["reconciler"]["authority"] == "chair"


def test_reviewers_cannot_write_to_the_repo() -> None:
    """A reviewer READS. Write and Edit must not be reachable from a reviewing role."""
    d = doc()
    allow = set(d["tool_policy"]["allow"])
    assert "Edit" in set(d["tool_policy"]["deny"])
    for name in ("senior-reviewer", "security-reviewer", "consistency-reviewer"):
        tools = set(d["roles"][name]["tool_permissions"])
        assert not any(t.startswith("Write") for t in tools), f"{name} can write"
        assert tools <= allow, f"{name} requests a tool the policy does not allow"


def test_author_exclusion_gate_rejects_the_author_reviewing_their_own_diff() -> None:
    d = doc()
    assert kit.evaluate_gate(d, "author-exclusion") is True
    assert (
        kit.evaluate_gate(d, "author-exclusion", {"author_is_reviewer": True}) is False
    )
    assert kit.evaluate_gate(d, "author-exclusion", {"roles_dispatched": 2}) is False


def test_a_silent_reviewer_triggers_a_reprobe_with_an_independent_verify() -> None:
    """A repair loop without an independent verify stage is a retry that reports success."""
    d = doc()
    rl = next(s for s in d["stages"] if s["id"] == "null-result-reprobe")
    assert rl["kind"] == "repair_loop"
    assert rl["target"] == ["review-panel"]
    assert rl["max_attempts"] <= 2, "the card says re-run ONCE with a narrowed scope"
    assert rl["verify"]["kind"] == "gate", "no independent verify stage"
    assert rl["verify"]["gate"]["blocking"] is True


def test_the_barrier_rejects_a_receipt_masquerading_as_a_result() -> None:
    """cross-vendor-dispatch rule 1: a background receipt is not a review."""
    d = doc()
    bar = next(s for s in d["stages"] if s["id"] == "review-panel")["barrier"]
    joined = " ".join(bar["reject_result_matching"])
    assert "started in the background" in joined
    assert "Check /codex:status" in joined
    assert bar["verify_artifact_exists"] is True
    assert bar["on_partial"] != "fail" or bar["mode"] == "all"


def test_MUTATION_weakening_author_exclusion_removes_its_power() -> None:
    """Both-states on the MECHANISM: drop the author conjunct and the bad state now passes."""
    d = doc()
    bad = {"author_is_reviewer": True}
    assert kit.evaluate_gate(d, "author-exclusion", bad) is False

    weakened = kit.mutated(d)
    weakened["gates"]["author-exclusion"]["expression"] = "roles_dispatched >= 3"
    ctx = kit.worked_context(weakened)
    ctx.update(bad)
    assert (
        _expr.evaluate(
            weakened["gates"]["author-exclusion"]["expression"], ctx, strict=True
        )
        is True
    ), (
        "removing the author conjunct should have stopped the rejection; if not, this test was "
        "not measuring that conjunct"
    )


def test_MUTATION_dropping_the_author_exclusion_stage_is_rejected() -> None:
    kit.assert_rejected(
        kit.drop_stage(doc(), "author-exclusion"), "author-exclusion gate removed"
    )


def test_MUTATION_a_role_requesting_a_denied_tool_is_rejected() -> None:
    """DSL-SEM-011: deny-by-default must actually bind the roles."""
    d = kit.mutated(doc())
    d["roles"]["senior-reviewer"]["tool_permissions"].append("Bash")
    kit.assert_rejected(d, "a reviewer granted an unrestricted shell")
