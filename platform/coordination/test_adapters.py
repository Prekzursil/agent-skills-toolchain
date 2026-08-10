"""Adapter boundaries: the refusal is loud, typed, BLOCKED, and preserves the artifact."""

from __future__ import annotations

from pathlib import Path

import pytest
import vendor_identity

from coordination.adapters import (
    AdapterStatus,
    CapabilityProfile,
    VendorAdapter,
    load_adapter_registry,
    preserve,
    route,
)
from coordination.capability import NegotiationVerdict, default_registry
from coordination.errors import CapabilityUnavailable


def _registry():
    return load_adapter_registry()


def test_every_registered_adapter_resolves_to_a_canonical_vendor() -> None:
    """A vendor string nobody can resolve makes condition 9 uncomputable downstream."""
    for adapter_id in _registry().ids:
        adapter = _registry().get(adapter_id)
        assert adapter.vendor_canonical is not None, adapter_id
        assert adapter.establishes_distinctness() is True, adapter_id


def test_unknown_adapter_id_names_the_registered_ones() -> None:
    with pytest.raises(KeyError, match="registered:"):
        _registry().get("does-not-exist")


def test_gemini_adapter_is_declared_but_measures_nothing() -> None:
    """The honest empty adapter. Its whole job is to refuse rather than inherit."""
    gemini = _registry().get("gemini-cli")
    assert gemini.status is AdapterStatus.DECLARED_UNMEASURED
    assert gemini.profile.offers == frozenset()
    assert gemini.profile.refuses == frozenset()
    result = gemini.negotiate(["fs.read", "fs.write", "proc.exec"])
    assert result.verdict is NegotiationVerdict.REFUSED
    assert len(result.blocking) == 3
    assert all("never measured" in f.reason for f in result.blocking)


def test_codex_refuses_owner_approval_so_such_units_cannot_route_there() -> None:
    """A runtime invoked with approvals bypassed structurally cannot pause for the owner."""
    codex = _registry().get("codex-cli")
    result = codex.negotiate(["interactive.owner_approval"])
    assert result.verdict is NegotiationVerdict.REFUSED
    human = _registry().get("human-owner")
    assert (
        human.negotiate(["interactive.owner_approval"]).verdict
        is NegotiationVerdict.AGREED
    )


def test_both_real_adapters_refuse_enforced_sandbox_and_that_only_degrades() -> None:
    for adapter_id in ("claude-code", "codex-cli"):
        adapter = _registry().get(adapter_id)
        result = adapter.negotiate(["fs.read", "sandbox.enforced"])
        assert result.verdict is NegotiationVerdict.DEGRADED, adapter_id
        assert result.may_proceed is True


def test_require_raises_typed_and_preserves_artifacts(tmp_path: Path) -> None:
    """Degrade loudly AND preserve: both halves of spec line 10983, in one call."""
    artifact = tmp_path / "partial.json"
    artifact.write_text('{"partial": true}', encoding="utf-8")
    codex = _registry().get("codex-cli")
    with pytest.raises(CapabilityUnavailable) as exc:
        codex.require(
            "interactive.owner_approval", unit_id="U-1", preserved_artifacts=[artifact]
        )
    assert exc.value.adapter_id == "codex-cli"
    assert exc.value.capability == "interactive.owner_approval"
    assert exc.value.preserved_artifacts == (str(artifact),)
    assert artifact.read_text(encoding="utf-8") == '{"partial": true}', (
        "artifact must survive"
    )


def test_require_distinguishes_measured_false_from_unmeasured() -> None:
    codex = _registry().get("codex-cli")
    with pytest.raises(CapabilityUnavailable, match="measured UNAVAILABLE"):
        codex.require("interactive.owner_approval", unit_id="U")
    gemini = _registry().get("gemini-cli")
    with pytest.raises(CapabilityUnavailable, match="never measured"):
        gemini.require("fs.read", unit_id="U")


def test_require_returns_none_when_offered() -> None:
    assert _registry().get("claude-code").require("fs.write", unit_id="U") is None


def test_degraded_outcome_is_structurally_incapable_of_reading_as_success() -> None:
    """No SUCCESS terminal state, and ``ok`` is a property that cannot be set."""
    outcome = (
        _registry()
        .get("gemini-cli")
        .degrade(
            unit_id="U-9",
            capability="fs.write",
            reason="unmeasured",
            preserved_artifacts=["a.json"],
        )
    )
    assert outcome.ok is False
    assert outcome.terminal_state == "BLOCKED"
    assert outcome.sentinel_line.startswith("FAILED:U-9 capability-unavailable")
    with pytest.raises((AttributeError, TypeError)):
        outcome.ok = True  # type: ignore[misc]


def test_blocked_is_not_failed() -> None:
    """BLOCKED says 'this adapter cannot'; FAILED would say 'attempted and went wrong'."""
    outcome = (
        _registry()
        .get("codex-cli")
        .degrade(unit_id="U", capability="subagent.spawn", reason="single-threaded")
    )
    assert outcome.terminal_state == "BLOCKED"
    assert outcome.to_dict()["terminal_state"] != "FAILED"


def test_preserve_keeps_missing_paths_in_the_record(tmp_path: Path) -> None:
    """A missing artifact is information the receipt must carry, not a reason to shorten the list."""
    present = tmp_path / "there.json"
    present.write_text("{}", encoding="utf-8")
    kept = preserve([present, tmp_path / "gone.json"])
    assert len(kept) == 2


def test_cross_vendor_comparison_is_canonical_not_string_equality() -> None:
    """The D1 lesson at the adapter plane: alias spellings must fold to one vendor."""
    claude = _registry().get("claude-code")
    codex = _registry().get("codex-cli")
    assert claude.is_cross_vendor_with(codex) is vendor_identity.Comparison.CROSS_VENDOR
    assert (
        claude.is_cross_vendor_with("Anthropic ")
        is vendor_identity.Comparison.SAME_VENDOR
    )
    assert (
        claude.is_cross_vendor_with("claude") is vendor_identity.Comparison.SAME_VENDOR
    )
    assert (
        claude.is_cross_vendor_with("bedrock")
        is vendor_identity.Comparison.NOT_COMPUTABLE
    )


def test_route_returns_every_candidate_and_never_picks_one() -> None:
    """No fallback chain: a substitution the caller did not ask for is the interchangeability lie."""
    reg = _registry()
    decision = route(
        "U-42",
        ["fs.read", "fs.write", "interactive.owner_approval"],
        [reg.get(a) for a in ("claude-code", "codex-cli", "gemini-cli", "human-owner")],
    )
    assert set(decision.negotiations) == {
        "claude-code",
        "codex-cli",
        "gemini-cli",
        "human-owner",
    }
    assert not hasattr(decision, "chosen")
    assert "claude-code" in decision.agreed
    assert "human-owner" in decision.agreed
    assert set(decision.refused) == {"codex-cli", "gemini-cli"}
    assert decision.any_eligible is True


def test_route_with_no_eligible_adapter_says_so_rather_than_returning_a_best_effort() -> (
    None
):
    reg = _registry()
    decision = route("U-0", ["interactive.owner_approval"], [reg.get("gemini-cli")])
    assert decision.any_eligible is False
    assert decision.agreed == () and decision.degraded == ()


def test_adapter_serialisation_includes_the_measured_split() -> None:
    payload = _registry().get("codex-cli").to_dict()
    assert payload["vendor_canonical"] == "openai"
    assert "sandbox.enforced" in payload["profile"]["refuses"]
    assert "artifact.output_file" in payload["profile"]["offers"]


def test_a_hand_built_adapter_with_an_unresolvable_vendor_is_not_distinct() -> None:
    """Guards the over-folding direction: a hosting plane must not establish distinctness."""
    adapter = VendorAdapter(
        adapter_id="hosted",
        vendor="bedrock",
        tool="whatever",
        status=AdapterStatus.DECLARED_UNMEASURED,
        profile=CapabilityProfile("hosted"),
    )
    assert adapter.establishes_distinctness() is False


def test_every_capability_named_by_an_adapter_is_registered() -> None:
    """A typo in an adapter's offers/refuses list would be SILENT.

    ``CapabilityProfile.support`` only validates an id when something asks about it, so a
    misspelled entry in ``offers`` never matches and the capability quietly degrades to UNMEASURED.
    That fails closed (the safe direction) but hides the misconfiguration, and a hidden
    misconfiguration in a registry is how a measured-true capability silently stops being offered.
    Validating the whole product up front turns it into a red suite instead.
    """
    registered = set(default_registry().ids)
    unknown: dict[str, list[str]] = {}
    total = 0
    for adapter_id in _registry().ids:
        adapter = _registry().get(adapter_id)
        named = sorted(adapter.profile.offers | adapter.profile.refuses)
        total += len(named)
        bad = [c for c in named if c not in registered]
        if bad:
            unknown[adapter_id] = bad
    assert unknown == {}, unknown
    assert total > 0, "an all-empty registry product would make this gate vacuous"


def test_the_registry_cross_check_can_actually_fail() -> None:
    """Detector control for the gate above, on a synthetic bad profile."""
    bad = CapabilityProfile("typo-adapter", offers=frozenset({"fs.raed"}))
    registered = set(default_registry().ids)
    assert [c for c in bad.offers if c not in registered] == ["fs.raed"]
