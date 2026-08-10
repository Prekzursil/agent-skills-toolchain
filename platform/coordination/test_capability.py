"""Capability negotiation: three-valued, fail-closed, and never silently interchangeable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from coordination.capability import (
    CAPABILITY_REGISTRY_PATH,
    CapabilityProfile,
    Criticality,
    NegotiationVerdict,
    Support,
    default_registry,
    load_capability_registry,
    negotiate,
)
from coordination.errors import UnknownCapability


def test_registry_loads_and_every_entry_declares_provenance() -> None:
    reg = default_registry()
    assert reg.ids, "an empty capability registry would make every negotiation vacuous"
    for cap_id in reg.ids:
        cap = reg.get(cap_id)
        assert cap.provenance.strip(), f"{cap_id} has no provenance"
        assert isinstance(cap.criticality, Criticality)


def test_degradable_capabilities_all_carry_a_degradation_note() -> None:
    """A DEGRADABLE capability with no note gives a caller nothing to record on the receipt."""
    reg = default_registry()
    missing = [
        cid
        for cid in reg.ids
        if reg.get(cid).criticality is Criticality.DEGRADABLE
        and not (reg.get(cid).degradation_note or "").strip()
    ]
    assert missing == []


def test_no_capability_claims_to_be_verified_by_this_unit() -> None:
    """Honesty gate: every entry is LEDGER-RECORDED, none was re-measured by this build.

    If a future unit measures one, it must flip this flag AND this assertion, which forces the
    claim to be made deliberately rather than by drift.
    """
    reg = default_registry()
    assert [c for c in reg.ids if reg.get(c).verified_by_this_unit] == []


def test_unknown_capability_raises_rather_than_being_skipped() -> None:
    """A typo must not silently make a required capability optional."""
    profile = CapabilityProfile("x", offers=frozenset({"fs.read"}))
    with pytest.raises(UnknownCapability, match="not in"):
        negotiate(["fs.raed"], profile)


def test_unmeasured_is_not_offered() -> None:
    """The asymmetry that closed D1, applied here: 'not listed' means 'not available'."""
    profile = CapabilityProfile("bare")
    assert profile.support("fs.read") is Support.UNMEASURED
    result = negotiate(["fs.read"], profile)
    assert result.verdict is NegotiationVerdict.REFUSED
    assert [f.capability for f in result.blocking] == ["fs.read"]
    assert "UNMEASURED is not OFFERED" in result.blocking[0].reason


def test_profile_cannot_offer_and_refuse_the_same_capability() -> None:
    with pytest.raises(UnknownCapability, match="both offers and refuses"):
        CapabilityProfile(
            "bad", offers=frozenset({"fs.read"}), refuses=frozenset({"fs.read"})
        )


def test_all_offered_is_agreed_and_asserts_the_positive() -> None:
    profile = CapabilityProfile("ok", offers=frozenset({"fs.read", "fs.write"}))
    result = negotiate(["fs.read", "fs.write"], profile)
    assert result.verdict is NegotiationVerdict.AGREED
    assert set(result.satisfied) == {"fs.read", "fs.write"}
    assert len(result.satisfied) == len(result.findings), (
        "N of N, not 'nothing blocking'"
    )
    assert result.sentinel_line.startswith("SUCCESS:negotiate/ok")


def test_refused_required_capability_blocks() -> None:
    profile = CapabilityProfile(
        "no-write", offers=frozenset({"fs.read"}), refuses=frozenset({"fs.write"})
    )
    result = negotiate(["fs.read", "fs.write"], profile)
    assert result.verdict is NegotiationVerdict.REFUSED
    assert result.may_proceed is False
    assert result.sentinel_line.startswith("FAILED:negotiate/no-write")


def test_refused_degradable_capability_degrades_but_proceeds() -> None:
    """DEGRADED must never be reported as AGREED - that is what 'degrade loudly' means."""
    profile = CapabilityProfile(
        "inert-sandbox",
        offers=frozenset({"fs.read", "fs.write"}),
        refuses=frozenset({"sandbox.enforced"}),
    )
    result = negotiate(["fs.read", "fs.write", "sandbox.enforced"], profile)
    assert result.verdict is NegotiationVerdict.DEGRADED
    assert result.may_proceed is True
    assert result.is_agreed is False
    assert [f.capability for f in result.degraded] == ["sandbox.enforced"]
    assert "post-hoc" in result.degraded[0].reason.lower()


def test_mutually_exclusive_pair_is_refused_not_silently_resolved() -> None:
    """mcp.tools x schema.typed_output cannot both hold on codex-cli (issue #15451).

    Picking one silently is the failure; reporting the conflict is the requirement.
    """
    profile = CapabilityProfile(
        "both", offers=frozenset({"mcp.tools", "schema.typed_output"})
    )
    result = negotiate(["mcp.tools", "schema.typed_output"], profile)
    assert result.verdict is NegotiationVerdict.REFUSED
    assert result.conflicts and result.conflicts[0][0] == "mcp.tools"
    assert "15451" in result.conflicts[0][2]


def test_negotiation_order_does_not_affect_the_verdict() -> None:
    profile = CapabilityProfile("p", offers=frozenset({"fs.read", "fs.write"}))
    a = negotiate(["fs.read", "fs.write"], profile)
    b = negotiate(["fs.write", "fs.read", "fs.read"], profile)
    assert a.verdict is b.verdict
    assert a.satisfied == b.satisfied


def test_empty_requirement_set_is_agreed_with_zero_findings() -> None:
    """Vacuous by construction, and stated: a unit that requires nothing negotiates trivially."""
    result = negotiate([], CapabilityProfile("p"))
    assert result.verdict is NegotiationVerdict.AGREED
    assert result.findings == ()
    assert result.satisfied == ()


def test_registry_file_is_valid_json_and_has_no_duplicate_ids(tmp_path: Path) -> None:
    raw = json.loads(CAPABILITY_REGISTRY_PATH.read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in raw["capabilities"]]
    assert len(ids) == len(set(ids))
    duplicated = {**raw, "capabilities": raw["capabilities"] + [raw["capabilities"][0]]}
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(duplicated), encoding="utf-8")
    with pytest.raises(UnknownCapability, match="duplicate capability id"):
        load_capability_registry(path)


def test_negotiation_serialises_with_every_finding() -> None:
    profile = CapabilityProfile(
        "p", offers=frozenset({"fs.read"}), refuses=frozenset({"fs.write"})
    )
    payload = negotiate(["fs.read", "fs.write"], profile).to_dict()
    assert payload["kind"] == "capability_negotiation"
    assert len(payload["findings"]) == 2
    assert payload["verdict"] == "REFUSED"
    assert payload["blocking"][0]["capability"] == "fs.write"
