"""CNL-0114 multi-interest family: typed-delta presets + instantiation + profiles.

Negotiation vs mediation is not a name split. Negotiation has no third-party
reframe seat and treats BATNA walk-away as a first-class stop. Mediation seats
a non-voting mediator whose only power is caucus/reframe/certify.

Adversarial collaboration refuses a split verdict: the product is a shared
pre-registered test. A lay panel disenfranchises the presenting expert and
forbids that expert's recommendation as a ballot default.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "council-preset.schema.json"
TASK_PATH = HERE / "fixtures" / "task.json"
SIBLING_PATH = HERE / "fixtures" / "sibling-library.json"

PROFILE_AXES = (
    "role_ids",
    "franchise",
    "protocol_bindings",
    "voting_method",
    "stopping_expression",
    "third_party_kind",
    "outcome_primary",
    "split_verdict_is_fault",
    "presenter_disenfranchised",
    "ballot_forbids_expert_default",
    "batna_is_first_class_outcome",
    "mediator_cannot_vote",
    "prereg_hash_required",
)

LOCKED_DIALS = (
    "voting.method",
    "third_party.kind",
    "franchise_rule",
    "integrity.split_verdict_is_fault",
    "integrity.presenter_disenfranchised",
    "integrity.ballot_forbids_expert_default",
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def family_presets() -> list[dict]:
    common_meta = {
        "unit_id": "CNL-0114",
        "library_c_id": "NOT-ON-DISK",
        "not_a_rename_of_sibling": True,
        "reconstruction_note": (
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; "
            "C-ids from that library are NOT-CHECKED."
        ),
    }
    negotiation = {
        "id": "council.preset.multi-interest.negotiation",
        "name": "Direct-bargain negotiation (parties only, BATNA-capable)",
        "family": "multi-interest",
        "base_spec": "councilspec.v2.minimal",
        "base_spec_version": "2.0.0",
        "delta": {
            "protocol_bindings": [
                "protocol.negotiation.offer",
                "protocol.negotiation.counter",
                "protocol.negotiation.package-swap",
                "protocol.negotiation.batna-check",
            ],
            "roles": [
                {"id": "party.A", "template": "bargainer", "votes": True},
                {"id": "party.B", "template": "bargainer", "votes": True},
                {"id": "recorder", "template": "scribe", "votes": False, "authority": "transcript-only"},
            ],
            "voting": {"method": "unanimous-consent-of-franchise", "quorum": 2, "author_votes": False},
            "stopping": {
                "expression": "all_franchise_signed OR batna_invoked OR max_rounds>=6",
                "max_rounds": 6,
            },
            "third_party": {
                "kind": "none",
                "votes": False,
                "may_reframe_interests": False,
                "may_lock_prereg": False,
                "may_strip_recommendations": False,
            },
            "franchise_rule": "parties-only",
            "anonymity": {"level": "named", "lift_phase": "never-hidden"},
            "recruitment": {"mode": "parties-are-given", "min_reviewers": 0},
            "evidence": {"tier": "party-offers", "clerk_gate": False, "prereg_hash_required": False},
            "integrity": {
                "split_verdict_is_fault": False,
                "presenter_disenfranchised": False,
                "ballot_forbids_expert_default": False,
                "mediator_cannot_vote": False,
                "batna_is_first_class_outcome": True,
            },
            "outcomes": ["agreement", "walk-away-batna"],
            "budgets": {"turns": 12, "caucus_turns": 0},
        },
        "default_binding": {
            "protocol": "protocol.negotiation.offer",
            "family": "MULTI-INTEREST",
        },
        "editable_dials": ["stopping.max_rounds", "budgets.turns"],
        "on_base_version_bump": "migrate-listed-dials-or-park",
        "supersedes_or_extends": [
            "CNL-0050-protocol-gap:negotiation-absent-from-58-cards",
            "CNL-0017-stakeholder-balance (parties as given interests, not a diversity sampler)",
        ],
        "meta": dict(common_meta),
    }
    mediation = {
        "id": "council.preset.multi-interest.mediation",
        "name": "Interest-reframe mediation (non-voting mediator)",
        "family": "multi-interest",
        "base_spec": "councilspec.v2.minimal",
        "base_spec_version": "2.0.0",
        "delta": {
            "protocol_bindings": [
                "protocol.mediation.private-caucus",
                "protocol.mediation.interest-reframe",
                "protocol.mediation.option-generation",
                "protocol.mediation.reality-test",
                "protocol.mediation.memorandum",
            ],
            "roles": [
                {"id": "party.A", "template": "bargainer", "votes": True},
                {"id": "party.B", "template": "bargainer", "votes": True},
                {
                    "id": "mediator",
                    "template": "neutral-reframer",
                    "votes": False,
                    "authority": "caucus-reframe-certify",
                },
                {"id": "recorder", "template": "scribe", "votes": False, "authority": "transcript-only"},
            ],
            "voting": {
                "method": "mediated-consent-parties-sign-mediator-certifies",
                "quorum": 2,
                "author_votes": False,
                "certifier": "mediator",
            },
            "stopping": {
                "expression": "memorandum_certified OR mediator_impasse OR max_rounds>=8",
                "max_rounds": 8,
            },
            "third_party": {
                "kind": "mediator",
                "votes": False,
                "may_reframe_interests": True,
                "may_lock_prereg": False,
                "may_strip_recommendations": False,
            },
            "franchise_rule": "parties-only-mediator-certifies",
            "anonymity": {"level": "named-plus-private-caucus", "lift_phase": "memorandum"},
            "recruitment": {"mode": "parties-plus-appointed-mediator", "min_reviewers": 0},
            "evidence": {"tier": "interest-statements", "clerk_gate": False, "prereg_hash_required": False},
            "integrity": {
                "split_verdict_is_fault": False,
                "presenter_disenfranchised": False,
                "ballot_forbids_expert_default": False,
                "mediator_cannot_vote": True,
                "batna_is_first_class_outcome": False,
            },
            "outcomes": ["certified-memorandum", "impasse"],
            "budgets": {"turns": 16, "caucus_turns": 4},
        },
        "default_binding": {
            "protocol": "protocol.mediation.private-caucus",
            "family": "MULTI-INTEREST",
        },
        "editable_dials": ["stopping.max_rounds", "budgets.caucus_turns"],
        "on_base_version_bump": "migrate-listed-dials-or-park",
        "supersedes_or_extends": [
            "CNL-0017-stakeholder-balance",
            "CNL-0050-protocol-gap:negotiation-is-not-mediation",
        ],
        "meta": dict(common_meta),
    }
    adv = {
        "id": "council.preset.multi-interest.adversarial-collaboration",
        "name": "Adversarial collaboration to a shared pre-registered test",
        "family": "multi-interest",
        "base_spec": "councilspec.v2.minimal",
        "base_spec_version": "2.0.0",
        "delta": {
            "protocol_bindings": [
                "protocol.advcol.competing-hypotheses",
                "protocol.advcol.joint-test-design",
                "protocol.advcol.preregister-lock",
                "protocol.advcol.execute-or-schedule",
                "protocol.advcol.shared-readout",
            ],
            "roles": [
                {"id": "advocate.A", "template": "hypothesis-holder", "votes": False, "authority": "sign-test"},
                {"id": "advocate.B", "template": "hypothesis-holder", "votes": False, "authority": "sign-test"},
                {
                    "id": "registrar",
                    "template": "prereg-lock",
                    "votes": False,
                    "authority": "lock-hash-reject-split-verdict",
                },
                {
                    "id": "protocol-adjudicator",
                    "template": "procedure-judge",
                    "votes": False,
                    "authority": "procedure-not-outcome",
                },
            ],
            "voting": {"method": "joint-prereg-lock-no-outcome-vote", "quorum": 0, "author_votes": False},
            "stopping": {
                "expression": "(prereg_locked AND (result_recorded OR run_scheduled)) OR registrar_rejects_split_verdict",
                "max_rounds": 5,
            },
            "third_party": {
                "kind": "registrar",
                "votes": False,
                "may_reframe_interests": False,
                "may_lock_prereg": True,
                "may_strip_recommendations": False,
            },
            "franchise_rule": "no-outcome-vote-advocates-sign-test",
            "anonymity": {"level": "named", "lift_phase": "never-hidden"},
            "recruitment": {"mode": "advocates-are-given", "min_reviewers": 0},
            "evidence": {"tier": "preregistered-test", "clerk_gate": False, "prereg_hash_required": True},
            "integrity": {
                "split_verdict_is_fault": True,
                "presenter_disenfranchised": False,
                "ballot_forbids_expert_default": False,
                "mediator_cannot_vote": False,
                "batna_is_first_class_outcome": False,
            },
            "outcomes": ["shared-test-result", "procedure-fault"],
            "budgets": {"turns": 14, "caucus_turns": 0},
        },
        "default_binding": {
            "protocol": "protocol.advcol.competing-hypotheses",
            "family": "MULTI-INTEREST",
        },
        "editable_dials": ["stopping.max_rounds", "budgets.turns"],
        "on_base_version_bump": "migrate-listed-dials-or-park",
        "supersedes_or_extends": [
            "CNL-0019-adversarial-selection-without-theatre",
            "CNL-0019-real-prior-conflict-must-bind-a-shared-test",
        ],
        "meta": dict(common_meta),
    }
    lay = {
        "id": "council.preset.multi-interest.lay-panel",
        "name": "Lay stakeholder panel with clerk-gated expert testimony",
        "family": "multi-interest",
        "base_spec": "councilspec.v2.minimal",
        "base_spec_version": "2.0.0",
        "delta": {
            "protocol_bindings": [
                "protocol.lay.clerk-packet",
                "protocol.lay.timeboxed-testimony",
                "protocol.lay.clerk-steering-rebuttal",
                "protocol.lay.silent-ballot",
            ],
            "roles": [
                {"id": "lay", "template": "stakeholder-decider", "votes": True, "count": 3},
                {
                    "id": "expert-presenter",
                    "template": "briefing-witness",
                    "votes": False,
                    "authority": "timeboxed-testimony-no-vote",
                },
                {
                    "id": "evidence-clerk",
                    "template": "packet-gate",
                    "votes": False,
                    "authority": "strip-recommendations",
                },
                {
                    "id": "chair",
                    "template": "procedure-only",
                    "votes": False,
                    "authority": "procedure",
                },
            ],
            "voting": {"method": "lay-only-secret-ballot", "quorum": 3, "author_votes": False},
            "stopping": {
                "expression": "ballots_cast>=quorum AND expert_recommendation_absent_from_ballot_options",
                "max_rounds": 3,
            },
            "third_party": {
                "kind": "evidence-clerk",
                "votes": False,
                "may_reframe_interests": False,
                "may_lock_prereg": False,
                "may_strip_recommendations": True,
            },
            "franchise_rule": "lay-only-secret-ballot",
            "anonymity": {"level": "secret-ballot", "lift_phase": "after-count"},
            "recruitment": {"mode": "lay-stakeholders-are-given", "min_reviewers": 3},
            "evidence": {"tier": "clerk-gated-packet", "clerk_gate": True, "prereg_hash_required": False},
            "integrity": {
                "split_verdict_is_fault": False,
                "presenter_disenfranchised": True,
                "ballot_forbids_expert_default": True,
                "mediator_cannot_vote": False,
                "batna_is_first_class_outcome": False,
            },
            "outcomes": ["lay-ballot-result"],
            "budgets": {"turns": 8, "caucus_turns": 0},
        },
        "default_binding": {
            "protocol": "protocol.lay.clerk-packet",
            "family": "MULTI-INTEREST",
        },
        "editable_dials": ["stopping.max_rounds", "roles[id=lay].count"],
        "on_base_version_bump": "migrate-listed-dials-or-park",
        "supersedes_or_extends": [
            "CNL-0017-stakeholder-balance (lay seats, not expert diversity)",
            "CNL-0034-jury-topology (related; CNL-0113 owns evidence juries — this is a stakeholder panel)",
        ],
        "meta": dict(common_meta),
    }
    return [negotiation, mediation, adv, lay]


def load_task() -> dict:
    return _load(TASK_PATH)


def load_siblings() -> list[dict]:
    doc = _load(SIBLING_PATH)
    return list(doc.get("records") or [])


def library_status() -> dict:
    return _load(SIBLING_PATH)["library_status"]


def _expand_roles(preset: dict, task: dict) -> list[dict]:
    d = preset["delta"]
    out: list[dict] = []
    parties = list(task.get("parties") or [])
    lays = list(task.get("lay_stakeholders") or [])
    party_i = 0
    lay_i = 0
    for role in d["roles"]:
        rid = role["id"]
        n = int(role.get("count") or 1)
        for k in range(n):
            seat = {
                "role_id": rid if n == 1 else f"{rid}.{k+1}",
                "template": role["template"],
                "votes": bool(role["votes"]),
                "authority": role.get("authority"),
            }
            if rid in {"party.A", "party.B", "advocate.A", "advocate.B"} and party_i < len(parties):
                seat["filled_by"] = parties[party_i]["id"]
                seat["interest"] = parties[party_i].get("interest")
                party_i += 1
            elif rid == "lay" and lay_i < len(lays):
                seat["filled_by"] = lays[lay_i]["id"]
                lay_i += 1
            elif rid == "expert-presenter":
                rec = task.get("expert_recommendation") or {}
                seat["filled_by"] = rec.get("presenter_id")
                seat["must_not_vote"] = True
            out.append(seat)
    return out


def instantiate(preset: dict, task: dict | None = None) -> dict:
    task = task or load_task()
    d = preset["delta"]
    roster = _expand_roles(preset, task)
    franchise = tuple(sorted(s["role_id"] for s in roster if s["votes"]))
    return {
        "preset_id": preset["id"],
        "task_id": task["id"],
        "roster": roster,
        "protocol_schedule": list(d["protocol_bindings"]),
        "voting_method": d["voting"]["method"],
        "stopping_expression": d["stopping"]["expression"],
        "third_party_kind": d["third_party"]["kind"],
        "franchise": list(franchise),
        "outcomes": list(d["outcomes"]),
        "integrity": dict(d["integrity"]),
        "evidence": dict(d["evidence"]),
        "default_binding": dict(preset["default_binding"]),
    }


def profile_of_instance(inst: dict) -> dict:
    role_ids = tuple(sorted({s["role_id"].split(".")[0] for s in inst["roster"]}))
    integ = inst.get("integrity") or {}
    ev = inst.get("evidence") or {}
    return {
        "role_ids": role_ids,
        "franchise": tuple(sorted(inst.get("franchise") or [])),
        "protocol_bindings": tuple(inst.get("protocol_schedule") or []),
        "voting_method": inst.get("voting_method"),
        "stopping_expression": inst.get("stopping_expression"),
        "third_party_kind": inst.get("third_party_kind"),
        "outcome_primary": (inst.get("outcomes") or [None])[0],
        "split_verdict_is_fault": bool(integ.get("split_verdict_is_fault")),
        "presenter_disenfranchised": bool(integ.get("presenter_disenfranchised")),
        "ballot_forbids_expert_default": bool(integ.get("ballot_forbids_expert_default")),
        "batna_is_first_class_outcome": bool(integ.get("batna_is_first_class_outcome")),
        "mediator_cannot_vote": bool(integ.get("mediator_cannot_vote")),
        "prereg_hash_required": bool(ev.get("prereg_hash_required")),
    }


def profile_of_preset(preset: dict, task: dict | None = None) -> dict:
    return profile_of_instance(instantiate(preset, task))


def profile_of_sibling(rec: dict) -> dict:
    """Adapter from reconstructed sibling records (not family-schema instances)."""
    d = rec.get("delta") or rec
    roles = d.get("roles") or []
    role_ids = tuple(sorted(r["id"] for r in roles))
    franchise = tuple(sorted(r["id"] for r in roles if r.get("votes")))
    voting = d.get("voting") or {}
    stopping = d.get("stopping") or {}
    third = d.get("third_party") or {}
    integ = d.get("integrity") or {}
    ev = d.get("evidence") or {}
    outcomes = d.get("outcomes") or [None]
    return {
        "role_ids": role_ids,
        "franchise": franchise,
        "protocol_bindings": tuple(d.get("protocol_bindings") or []),
        "voting_method": voting.get("method"),
        "stopping_expression": stopping.get("expression"),
        "third_party_kind": third.get("kind") or "none",
        "outcome_primary": outcomes[0],
        "split_verdict_is_fault": bool(integ.get("split_verdict_is_fault")),
        "presenter_disenfranchised": bool(integ.get("presenter_disenfranchised")),
        "ballot_forbids_expert_default": bool(integ.get("ballot_forbids_expert_default")),
        "batna_is_first_class_outcome": bool(integ.get("batna_is_first_class_outcome")),
        "mediator_cannot_vote": bool(integ.get("mediator_cannot_vote")),
        "prereg_hash_required": bool(ev.get("prereg_hash_required")),
    }


def distance(a: dict, b: dict) -> int:
    return sum(1 for k in PROFILE_AXES if a.get(k) != b.get(k))


def name_only_clone(preset: dict, new_id: str, new_name: str) -> dict:
    cloned = copy.deepcopy(preset)
    cloned["id"] = new_id
    cloned["name"] = new_name
    return cloned


class LockedDialError(ValueError):
    pass


def apply_operator_overlay(preset: dict, overlay: dict) -> dict:
    """Reject overlays that touch dials not listed in editable_dials."""
    allowed = set(preset.get("editable_dials") or [])
    illegal = [k for k in overlay if k not in allowed]
    if illegal:
        raise LockedDialError(
            "overlay touches non-editable dial(s): " + ",".join(sorted(illegal))
        )
    out = copy.deepcopy(preset)
    for key, val in overlay.items():
        cursor = out["delta"]
        parts = key.split(".")
        for p in parts[:-1]:
            cursor = cursor[p]
        cursor[parts[-1]] = val
    return out


def lay_ballot_steering(options: list[str], expert_recommendation_label: str) -> dict:
    """FIRES when the expert's recommended option is a ballot default."""
    fired = expert_recommendation_label in options
    return {
        "check": "lay-panel-expert-steering",
        "fires": fired,
        "reject_state": "expert recommendation appears as a ballot option/default",
        "options": options,
        "expert_recommendation_label": expert_recommendation_label,
    }


def split_verdict_fault(claimed_outcome: str, prereg_locked: bool, preset: dict) -> dict:
    """FIRES when adversarial-collaboration emits a split verdict."""
    must_fault = bool(preset["delta"]["integrity"]["split_verdict_is_fault"])
    is_split = claimed_outcome == "split-verdict"
    fired = must_fault and (is_split or not prereg_locked and is_split)
    if must_fault and is_split:
        fired = True
    return {
        "check": "adversarial-collaboration-split-verdict",
        "fires": fired,
        "reject_state": "split-verdict claimed instead of a locked shared test",
        "claimed_outcome": claimed_outcome,
        "prereg_locked": prereg_locked,
    }


def mediation_without_mediator(preset: dict) -> dict:
    """FIRES when a record named mediation has third_party.kind != mediator."""
    named = "mediation" in str(preset.get("id", "")).lower() or "mediation" in str(
        preset.get("name", "")
    ).lower()
    kind = preset["delta"]["third_party"]["kind"]
    fired = named and kind != "mediator"
    return {
        "check": "mediation-requires-nonvoting-mediator",
        "fires": fired,
        "reject_state": "id/name says mediation but third_party.kind is not mediator",
        "third_party_kind": kind,
    }


def nearest_sibling(preset: dict, siblings: list[dict], task: dict | None = None) -> dict:
    p = profile_of_preset(preset, task)
    ranked = []
    for rec in siblings:
        sp = profile_of_sibling(rec)
        dist = distance(p, sp)
        ranked.append({"id": rec["id"], "distance": dist, "duplicate": dist == 0})
    ranked.sort(key=lambda r: (r["distance"], r["id"]))
    dupes = [r for r in ranked if r["duplicate"] and r["id"] != preset["id"]]
    distinct = [r for r in ranked if not r["duplicate"]]
    nearest = distinct[0] if distinct else None
    return {
        "preset_id": preset["id"],
        "ranked": ranked,
        "duplicates": dupes,
        "nearest_distinct": nearest,
    }
