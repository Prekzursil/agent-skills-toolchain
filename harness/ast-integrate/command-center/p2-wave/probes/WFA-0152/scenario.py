"""Live scenarios for WFA-0152: publish both-states and install/rollback/re-resolve."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from common import HERE
from engine import (
    Consumer,
    FixtureMarketplace,
    PackError,
    load_json,
    required_bump,
    resolve_lineage,
)

FIXTURES = HERE / "fixtures"


def load_fixtures() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    certs = load_json(FIXTURES / "certs.json")
    lineage = load_json(FIXTURES / "lineage.json")
    v1 = load_json(FIXTURES / "pack-v1.0.0.json")
    v11 = load_json(FIXTURES / "pack-v1.1.0.json")
    return certs, lineage, v1, v11


def _refuse_publish(market: FixtureMarketplace, pack: dict[str, Any]) -> dict[str, Any]:
    try:
        market.publish(pack)
    except PackError as exc:
        return {"refused": True, "error": exc.as_dict()}
    return {"refused": False, "error": None}


def both_states_publish(root: Path) -> dict[str, Any]:
    """Uncertified pack refused; same pack with CERTIFIED workflows publishes."""
    certs, lineage, v1, v11 = load_fixtures()

    rejected_certs = deepcopy(certs)
    rejected_certs["wf-alpha@1.0.0"]["verdict"] = "REJECTED"
    bad_root = root / "uncertified"
    bad_market = FixtureMarketplace(bad_root, rejected_certs, lineage)
    uncertified = _refuse_publish(bad_market, v1)

    provisional_certs = deepcopy(certs)
    provisional_certs["wf-alpha@1.0.0"]["verdict"] = "PROVISIONAL"
    prov_market = FixtureMarketplace(root / "provisional", provisional_certs, lineage)
    provisional = _refuse_publish(prov_market, v1)

    absent_certs = deepcopy(certs)
    del absent_certs["wf-alpha@1.0.0"]
    absent_market = FixtureMarketplace(root / "absent", absent_certs, lineage)
    absent = _refuse_publish(absent_market, v1)

    good_market = FixtureMarketplace(root / "certified", certs, lineage)
    pub_v1 = good_market.publish(v1)

    patch_attempt = deepcopy(v11)
    patch_attempt["version"] = "1.0.1"
    insufficient = _refuse_publish(good_market, patch_attempt)

    pub_v11 = good_market.publish(v11)
    bump = required_bump(v1, v11)

    widen = deepcopy(v1)
    widen["presets"][0]["tool_permissions"] = ["Read", "Bash"]
    widen_market = FixtureMarketplace(root / "widen", certs, lineage)
    privilege = _refuse_publish(widen_market, widen)

    return {
        "uncertified": uncertified,
        "provisional": provisional,
        "absent_cert": absent,
        "certified_v1": pub_v1,
        "insufficient_bump": insufficient,
        "certified_v11": pub_v11,
        "required_bump_v1_to_v11": bump,
        "privilege_widen": privilege,
        "pass": bool(
            uncertified.get("refused")
            and uncertified.get("error", {}).get("code") == "uncertified-workflow"
            and uncertified.get("error", {}).get("workflow_id") == "wf-alpha"
            and uncertified.get("error", {}).get("verdict") == "REJECTED"
            and provisional.get("refused")
            and absent.get("refused")
            and pub_v1.get("artifact_digest")
            and pub_v11.get("artifact_digest")
            and bump == "minor"
            and insufficient.get("refused")
            and insufficient.get("error", {}).get("code") == "insufficient-bump"
            and privilege.get("refused")
            and privilege.get("error", {}).get("code") == "privilege-widen"
        ),
    }


def install_rollback_cycle(root: Path) -> dict[str, Any]:
    """Install 1.1.0, resolve, roll back to 1.0.0, re-resolve, compare lineage sets.

    Tamper control: drop wf-alpha lineage after publish; re-resolve names the gap.
    """
    certs, lineage, v1, v11 = load_fixtures()
    market = FixtureMarketplace(root / "market", certs, lineage)
    pub_v1 = market.publish(v1)
    pub_v11 = market.publish(v11)
    consumer = Consumer(market)

    first = consumer.install("foundry.retrieval", "1.0.0", "stable")
    installed = consumer.install("foundry.retrieval", "1.1.0", "stable")
    before = consumer.re_resolve()
    rolled = consumer.rollback()
    after = consumer.re_resolve()

    before_set = set(before["lineage_set"])
    after_set = set(after["lineage_set"])
    added = sorted(before_set - after_set)
    lost = sorted(after_set - before_set)
    expected_added = sorted(set(pub_v11["lineage_set"]) - set(pub_v1["lineage_set"]))

    # Tamper: drop alpha lineage, re-resolve must name it. Restore afterwards.
    saved_alpha = market.lineage.pop("wf-alpha@1.0.0")
    try:
        consumer.re_resolve()
        tamper = {"fired": False, "error": None}
    except PackError as exc:
        tamper = {"fired": True, "error": exc.as_dict()}
    market.lineage["wf-alpha@1.0.0"] = saved_alpha
    restored = consumer.re_resolve()

    # Dangling sources_unresolved on a published blob's lineage must also fire.
    market.lineage["wf-alpha@1.0.0"] = {
        **saved_alpha,
        "sources_unresolved": ["mech.planted-unresolved"],
    }
    try:
        consumer.re_resolve()
        dangling = {"fired": False, "error": None}
    except PackError as exc:
        dangling = {"fired": True, "error": exc.as_dict()}
    market.lineage["wf-alpha@1.0.0"] = saved_alpha
    restored2 = consumer.re_resolve()

    pass_ok = bool(
        first["version"] == "1.0.0"
        and installed["version"] == "1.1.0"
        and rolled["version"] == "1.0.0"
        and before["resolved"]
        and after["resolved"]
        and restored["resolved"]
        and restored2["resolved"]
        and added == expected_added
        and lost == []
        and "mech.fuse" in before_set
        and "mech.fuse" not in after_set
        and "mech.retrieve" in after_set
        and "mech.rank" in after_set
        and tamper["fired"]
        and "wf-alpha@1.0.0"
        in ((tamper.get("error") or {}).get("missing_records") or [])
        and dangling["fired"]
        and any(
            "mech.planted-unresolved" in s
            for s in ((dangling.get("error") or {}).get("unresolved_sources") or [])
        )
    )

    return {
        "published_v1_lineage": pub_v1["lineage_set"],
        "published_v11_lineage": pub_v11["lineage_set"],
        "first_install_version": first["version"],
        "install_version": installed["version"],
        "lineage_before_rollback": before["lineage_set"],
        "rollback_version": rolled["version"],
        "lineage_after_rollback": after["lineage_set"],
        "added_by_minor": added,
        "lost_on_rollback": lost,
        "every_ref_resolved_after_rollback": after["resolved"],
        "tamper_missing_record": tamper,
        "tamper_unresolved_source": dangling,
        "restored_resolves": restored2["resolved"],
        "compare": {
            "before_minus_after": added,
            "after_minus_before": lost,
            "equal_to_publication_delta": added == expected_added and lost == [],
        },
        "pass": pass_ok,
    }


def pack_contents_spec() -> dict[str, Any]:
    _, _, v1, _ = load_fixtures()
    return {
        "required_fields": [
            "pack_id",
            "name",
            "version",
            "channel",
            "workflows",
            "presets",
        ],
        "workflow_required_fields": [
            "workflow_id",
            "workflow_version",
            "certification_ref",
            "lineage_ref",
            "tool_permissions",
            "source_policy",
        ],
        "channels": ["stable", "beta", "nightly"],
        "example_pack_id": v1["pack_id"],
        "example_version": v1["version"],
        "preset_rule": "preset tool_permissions and source_policy must not widen the host workflow",
        "publish_rule": "every workflow must be CERTIFIED; sources_unresolved must be empty",
        "bump_rule": {
            "major": "workflow/preset removal, lineage_ref rewrite, privilege or source_policy widen, channel change",
            "minor": "additive workflows or presets",
            "patch": "metadata-only (name/license/publisher/description)",
        },
    }
