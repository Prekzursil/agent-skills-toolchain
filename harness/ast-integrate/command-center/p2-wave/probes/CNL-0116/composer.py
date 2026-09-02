#!/usr/bin/env python3
"""Flagship auto-composer for CNL-0116.

For an owner request with no preset named, derive roster / protocol schedule /
voting / stopping, attach a contestable explanation per dial, and apply a
one-step recorded override. Silent edits of non-editable dials are rejected.
"""
from __future__ import annotations

import math
import re
from typing import Any

TWENTY_KEYS: tuple[str, ...] = (
    "id",
    "name",
    "status",
    "base_spec_ref",
    "default_binding",
    "editable_dials",
    "charter",
    "participants",
    "roles",
    "engagement",
    "budgets",
    "evidence",
    "voting",
    "stopping",
    "outcomes",
    "integrity",
    "artifacts",
    "execution",
    "protocol_binding",
    "meta",
)

CORE_ROLES: tuple[str, ...] = (
    "Orchestrator",
    "Domain",
    "Adversary",
    "Evidence-auditor",
)

FEATURE_TRIGGERS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "legal",
        re.compile(
            r"\b(legal|lawful|gdpr|liabilit(?:y|ies)|contract|counsel|counsel's)\b",
            re.I,
        ),
        "Legal",
    ),
    (
        "security",
        re.compile(r"\b(secur(?:e|ity)|threat|exploit|cve|authn|authz|red-?team)\b", re.I),
        "Security",
    ),
    (
        "operator",
        re.compile(
            r"\b(production|deploy|on-call|outage|rollback|go/?\s*no-go|go-no-go)\b",
            re.I,
        ),
        "Operator",
    ),
)

RISK_CRITICAL = re.compile(
    r"\b(outage|irreversible|safety-critical|prod-down|data loss)\b", re.I
)
RISK_HIGH = re.compile(
    r"\b(production|security|gdpr|legal|release|go/?\s*no-go|go-no-go)\b", re.I
)
RISK_LOW = re.compile(r"\b(brainstorm|exploratory|typo|docs only|documentation-only)\b", re.I)

OUTCOMES: list[str] = [
    "decision",
    "conditional-decision",
    "no-decision",
    "irreducible-disagreement",
    "dissent-with-minority-report",
    "proof-of-impossibility",
]

EDITABLE_DIALS: tuple[str, ...] = (
    "charter.risk_tier",
    "roles",
    "protocol_binding.schedule",
    "voting.rule",
    "stopping.max_rounds",
    "stopping.expression",
    "budgets.max_rounds",
    "evidence.standard",
)

LOCKED_DIALS: frozenset[str] = frozenset(
    {
        "id",
        "default_binding",
        "integrity.silent_override_forbidden",
        "integrity.explanation_required",
        "meta.explanation_required",
    }
)

PURPOSE_CLASS = "general-unspecified-request"


class ComposerError(ValueError):
    pass


def _reason(dial: str, chosen: Any, default: Any, reason: str, grounded_in: str) -> dict:
    return {
        "dial": dial,
        "chosen": chosen,
        "default": default,
        "reason": reason,
        "grounded_in": grounded_in,
        "contestable": True,
    }


def infer_risk_tier(task: str, explicit: str | None = None) -> tuple[str, dict]:
    if explicit:
        return explicit, _reason(
            "charter.risk_tier",
            explicit,
            "medium",
            "owner supplied risk_tier in the one-step override or charter",
            "owner.override(charter.risk_tier)",
        )
    if RISK_CRITICAL.search(task):
        tier = "critical"
        why = "task names an irreversible / outage / safety class"
    elif RISK_HIGH.search(task):
        tier = "high"
        why = "task names production, security, legal, or go/no-go"
    elif RISK_LOW.search(task):
        tier = "low"
        why = "task names an exploratory / docs-only class"
    else:
        tier = "medium"
        why = "no risk cue; flagship default is medium, not the static 4-voice freeze"
    return tier, _reason("charter.risk_tier", tier, "medium", why, "task-text")


def feature_seats(task: str) -> tuple[list[str], list[dict]]:
    seats: list[str] = []
    notes: list[dict] = []
    for feature, pat, role in FEATURE_TRIGGERS:
        if pat.search(task):
            seats.append(role)
            notes.append(
                _reason(
                    f"roles.{role}",
                    role,
                    None,
                    f"task feature {feature!r} requires this seat",
                    f"feature:{feature}",
                )
            )
        else:
            notes.append(
                _reason(
                    f"roles.{role}.absent",
                    None,
                    None,
                    f"task has no {feature} cue; seating {role} would be a false positive",
                    f"feature:{feature}:absent",
                )
            )
    return seats, notes


def schedule_for(tier: str) -> tuple[list[str], dict]:
    table = {
        "low": ["intake", "consult", "decide"],
        "medium": ["intake", "propose", "critique", "revise", "decide"],
        "high": [
            "intake",
            "independent-draft",
            "red-team",
            "synthesis",
            "vote",
            "owner-checkpoint",
        ],
        "critical": [
            "intake",
            "independent-draft",
            "red-team",
            "synthesis",
            "executable-oracle",
            "vote",
            "owner-checkpoint",
        ],
    }
    if tier not in table:
        raise ComposerError(f"unknown risk_tier {tier!r}")
    sched = table[tier]
    return sched, _reason(
        "protocol_binding.schedule",
        sched,
        table["medium"],
        f"risk_tier={tier} selects this phase list (not a frozen consult)",
        f"risk_tier:{tier}",
    )


def voting_for(tier: str, n_seats: int) -> tuple[dict, list[dict]]:
    rules = {
        "low": "majority",
        "medium": "supermajority-2-3",
        "high": "unanimous-or-escalate",
        "critical": "unanimous-or-owner",
    }
    rule = rules[tier]
    if rule == "majority":
        quorum = max(2, math.ceil(n_seats / 2))
    elif rule == "supermajority-2-3":
        quorum = max(2, math.ceil(n_seats * 2 / 3))
    else:
        quorum = n_seats
    voting = {"rule": rule, "quorum": quorum}
    return voting, [
        _reason(
            "voting.rule",
            rule,
            "majority",
            f"risk_tier={tier} sets the vote rule; static sibling uses majority or unanimous-or-record-dissent",
            f"risk_tier:{tier}",
        ),
        _reason(
            "voting.quorum",
            quorum,
            n_seats,
            "quorum is a function of seat count and rule, not a frozen 4",
            f"n_seats:{n_seats}",
        ),
    ]


def stopping_for(tier: str) -> tuple[dict, list[dict]]:
    table = {
        "low": {
            "max_rounds": 2,
            "expression": "round>=2 OR majority",
            "on_timeout": "accept-majority",
        },
        "medium": {
            "max_rounds": 6,
            "expression": "no_new_objection_for_1_round OR round>=6",
            "on_timeout": "BLOCKED",
        },
        "high": {
            "max_rounds": 12,
            "expression": "consensus OR owner_checkpoint OR round>=12",
            "on_timeout": "BLOCKED",
        },
        "critical": {
            "max_rounds": 12,
            "expression": "executable_test_settled OR proof_of_impossibility OR owner_halt",
            "on_timeout": "BLOCKED",
        },
    }
    stop = dict(table[tier])
    return stop, [
        _reason(
            "stopping.max_rounds",
            stop["max_rounds"],
            6,
            f"risk_tier={tier} caps rounds; catalog-class sibling freezes 8",
            f"risk_tier:{tier}",
        ),
        _reason(
            "stopping.expression",
            stop["expression"],
            "round>=6",
            f"risk_tier={tier} stopping expression is declarative, not a runtime eval over prior_rounds",
            f"risk_tier:{tier}",
        ),
    ]


def evidence_for(tier: str) -> tuple[dict, dict]:
    standard = {
        "low": "asserted-ok",
        "medium": "cited-artifact",
        "high": "independent-second-signal",
        "critical": "executable-oracle-or-proof",
    }[tier]
    ev = {"standard": standard, "untrusted_transcript": True}
    return ev, _reason(
        "evidence.standard",
        standard,
        "cited-artifact",
        f"risk_tier={tier} sets the evidence bar",
        f"risk_tier:{tier}",
    )


def flagship_preset() -> dict:
    """Typed delta record: 20 keys, auto-compose binding, core roster only."""
    return {
        "id": "C-GP01",
        "name": "flagship-auto-composed",
        "status": "DESIGN",
        "base_spec_ref": "CouncilSpec/v2",
        "default_binding": "auto-compose",
        "editable_dials": list(EDITABLE_DIALS),
        "charter": {
            "objective": "unspecified-owner-request",
            "risk_tier": "derived",
            "desired_output": "decision-with-explanation",
            "success_criteria": "every-dial-explained-and-contestable",
            "consensus_intent": "derived",
        },
        "participants": {"mode": "auto-compose", "min_seats": 4, "max_seats": 8},
        "roles": list(CORE_ROLES),
        "engagement": {"style": "facilitated-deliberation", "asynchronous_ok": True},
        "budgets": {"max_rounds": "derived", "token_ceiling": "owner-constraint-or-default"},
        "evidence": {"standard": "derived", "untrusted_transcript": True},
        "voting": {"rule": "derived", "quorum": "derived"},
        "stopping": {
            "max_rounds": "derived",
            "expression": "derived",
            "on_timeout": "BLOCKED",
        },
        "outcomes": list(OUTCOMES),
        "integrity": {
            "explanation_required": True,
            "silent_override_forbidden": True,
            "anti_failure": {
                "on_split": "surface-disagreement",
                "no_silent_average": True,
            },
        },
        "artifacts": {
            "required": [
                "roster",
                "protocol_schedule",
                "voting",
                "stopping",
                "explanation",
                "overrides",
            ]
        },
        "execution": {
            "composer": "command-center/p2-wave/probes/CNL-0116/composer.py",
            "instantiate": "compose(task, risk_tier=None, override=None, named_preset=None)",
        },
        "protocol_binding": {"mode": "auto-compose", "schedule": "derived"},
        "meta": {
            "unit_id": "CNL-0116",
            "purpose_class": PURPOSE_CLASS,
            "supersedes": ["C-M01"],
            "extends": ["council.preset.catalog-class.editable"],
            "one_step_override": "owner.override(dial, value)",
            "explanation_required": True,
        },
    }


def _set_path(obj: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    cur: Any = obj
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def _get_path(obj: dict, path: str) -> Any:
    cur: Any = obj
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def check_integrity(instance: dict) -> list[str]:
    """Reject missing explanations and silent overrides."""
    errors: list[str] = []
    expl = instance.get("explanation") or []
    by_dial = {e.get("dial"): e for e in expl if isinstance(e, dict)}
    required = [
        "charter.risk_tier",
        "protocol_binding.schedule",
        "voting.rule",
        "stopping.expression",
    ]
    for dial in required:
        rec = by_dial.get(dial)
        if not rec or not str(rec.get("reason") or "").strip():
            errors.append(f"missing-explanation:{dial}")
    if instance.get("binding") == "auto-compose":
        if not instance.get("integrity", {}).get("silent_override_forbidden", False):
            errors.append("silent-override-not-forbidden")
        if instance.get("overrides") is None:
            errors.append("overrides-array-absent")
    for ov in instance.get("overrides") or []:
        if not ov.get("recorded"):
            errors.append("unrecorded-override")
        if ov.get("dial") in LOCKED_DIALS:
            errors.append(f"locked-dial-overridden:{ov.get('dial')}")
    return errors


def fingerprint(instance: dict) -> dict:
    roles = instance.get("roles") or []
    sched = instance.get("protocol_schedule") or instance.get("protocol_binding", {}).get(
        "schedule"
    ) or []
    voting = instance.get("voting") or {}
    stopping = instance.get("stopping") or {}
    return {
        "roles": sorted(roles),
        "protocol_schedule": list(sched) if not isinstance(sched, str) else [sched],
        "voting_rule": voting.get("rule"),
        "stopping_expression": stopping.get("expression"),
        "binding": instance.get("binding") or instance.get("default_binding"),
        "explanation_mandatory": bool(
            (instance.get("integrity") or {}).get("explanation_required")
        ),
        "purpose_class": (instance.get("meta") or {}).get("purpose_class")
        or instance.get("purpose_class"),
        "id": instance.get("id"),
    }


def distance(a: dict, b: dict) -> dict:
    fa, fb = fingerprint(a), fingerprint(b)
    axes = {
        "roles": set(fa["roles"]) != set(fb["roles"]),
        "protocol_schedule": tuple(fa["protocol_schedule"]) != tuple(fb["protocol_schedule"]),
        "voting_rule": fa["voting_rule"] != fb["voting_rule"],
        "stopping_expression": fa["stopping_expression"] != fb["stopping_expression"],
        "binding": fa["binding"] != fb["binding"],
        "explanation_mandatory": fa["explanation_mandatory"] != fb["explanation_mandatory"],
        "purpose_class": fa["purpose_class"] != fb["purpose_class"],
    }
    differed = [k for k, v in axes.items() if v]
    ra, rb = set(fa["roles"]), set(fb["roles"])
    union = ra | rb
    jaccard = 1.0 if not union else 1.0 - (len(ra & rb) / len(union))
    return {
        "integer_axes": len(differed),
        "differed": differed,
        "role_jaccard_distance": jaccard,
        "name_only": len(differed) == 0,
        "a_id": fa.get("id"),
        "b_id": fb.get("id"),
    }


def compose(
    task: str,
    risk_tier: str | None = None,
    override: dict | None = None,
    named_preset: str | None = None,
) -> dict:
    """Instantiate the flagship against an unnamed owner request."""
    if named_preset:
        return {
            "flagship_used": False,
            "path": "named-preset",
            "named_preset": named_preset,
            "binding": "named-preset",
            "reason": (
                "owner named a preset; flagship auto-compose is the unnamed path only"
            ),
        }
    preset = flagship_preset()
    override = dict(override or {})
    if "preset" in override:
        return compose(task, named_preset=str(override["preset"]))

    locked_attempt = [d for d in override if d in LOCKED_DIALS]
    if locked_attempt:
        raise ComposerError(
            "non-editable dial override rejected: " + ",".join(locked_attempt)
        )
    unknown = [d for d in override if d not in EDITABLE_DIALS and d not in LOCKED_DIALS]
    if unknown:
        raise ComposerError("unknown dial override rejected: " + ",".join(unknown))

    risk_over = override.get("charter.risk_tier")
    tier, tier_expl = infer_risk_tier(task, risk_over or risk_tier)
    extra, extra_expl = feature_seats(task)
    roles = list(CORE_ROLES)
    if "roles" in override:
        roles = list(override["roles"])
        extra_expl = [
            _reason(
                "roles",
                roles,
                list(CORE_ROLES),
                "owner one-step override replaced the auto-composed roster",
                "owner.override(roles)",
            )
        ]
    else:
        for r in extra:
            if r not in roles:
                roles.append(r)
        for role in CORE_ROLES:
            extra_expl.insert(
                0,
                _reason(
                    f"roles.{role}",
                    role,
                    None,
                    "flagship core seat; not the ECC Architect/Skeptic/Pragmatist/Critic freeze",
                    "core:C-GP01",
                ),
            )

    sched, sched_expl = schedule_for(tier)
    if "protocol_binding.schedule" in override:
        sched = list(override["protocol_binding.schedule"])
        sched_expl = _reason(
            "protocol_binding.schedule",
            sched,
            sched_expl["chosen"],
            "owner one-step override of protocol schedule",
            "owner.override(protocol_binding.schedule)",
        )
    voting, vote_expl = voting_for(tier, len(roles))
    if "voting.rule" in override:
        voting = dict(voting)
        voting["rule"] = override["voting.rule"]
        if voting["rule"] in {"unanimous-or-escalate", "unanimous-or-owner"}:
            voting["quorum"] = len(roles)
        vote_expl = [
            _reason(
                "voting.rule",
                voting["rule"],
                vote_expl[0]["chosen"],
                "owner one-step override of voting.rule",
                "owner.override(voting.rule)",
            ),
            vote_expl[1],
        ]
    stop, stop_expl = stopping_for(tier)
    if "stopping.max_rounds" in override:
        stop = dict(stop)
        stop["max_rounds"] = int(override["stopping.max_rounds"])
        stop_expl[0] = _reason(
            "stopping.max_rounds",
            stop["max_rounds"],
            stop_expl[0]["chosen"],
            "owner one-step override of stopping.max_rounds",
            "owner.override(stopping.max_rounds)",
        )
    if "stopping.expression" in override:
        stop = dict(stop)
        stop["expression"] = override["stopping.expression"]
        stop_expl[1] = _reason(
            "stopping.expression",
            stop["expression"],
            stop_expl[1]["chosen"],
            "owner one-step override of stopping.expression",
            "owner.override(stopping.expression)",
        )
    ev, ev_expl = evidence_for(tier)
    if "evidence.standard" in override:
        ev = dict(ev)
        ev["standard"] = override["evidence.standard"]
        ev_expl = _reason(
            "evidence.standard",
            ev["standard"],
            ev_expl["chosen"],
            "owner one-step override of evidence.standard",
            "owner.override(evidence.standard)",
        )
    max_rounds = stop["max_rounds"]
    if "budgets.max_rounds" in override:
        max_rounds = int(override["budgets.max_rounds"])
        bud_expl = _reason(
            "budgets.max_rounds",
            max_rounds,
            stop["max_rounds"],
            "owner one-step override of budgets.max_rounds",
            "owner.override(budgets.max_rounds)",
        )
    else:
        bud_expl = _reason(
            "budgets.max_rounds",
            max_rounds,
            6,
            "budget tracks stopping.max_rounds unless owner overrides it",
            "stopping.max_rounds",
        )

    flat: list[dict] = [tier_expl]
    if isinstance(sched_expl, dict):
        flat.append(sched_expl)
    flat.extend(vote_expl)
    flat.extend(stop_expl)
    flat.append(ev_expl)
    flat.append(bud_expl)
    flat.extend(extra_expl)

    overrides_rec = []
    for dial, value in override.items():
        overrides_rec.append(
            {
                "dial": dial,
                "value": value,
                "recorded": True,
                "path": "owner.override(dial, value)",
            }
        )

    instance = {
        "id": "C-GP01",
        "name": "flagship-auto-composed",
        "flagship_used": True,
        "path": "auto-compose",
        "binding": "auto-compose",
        "purpose_class": PURPOSE_CLASS,
        "task": task,
        "roles": roles,
        "protocol_schedule": sched,
        "protocol_binding": {"mode": "auto-compose", "schedule": sched},
        "voting": voting,
        "stopping": stop,
        "evidence": ev,
        "budgets": {"max_rounds": max_rounds},
        "charter": {
            "objective": "unspecified-owner-request",
            "risk_tier": tier,
            "desired_output": "decision-with-explanation",
        },
        "integrity": dict(preset["integrity"]),
        "meta": dict(preset["meta"]),
        "explanation": flat,
        "overrides": overrides_rec,
        "one_step_override_path": "owner.override(dial, value)",
        "default_binding": "auto-compose",
    }
    errs = check_integrity(instance)
    if errs:
        raise ComposerError("integrity: " + ";".join(errs))
    return instance


def preset_from_static_sibling(row: dict) -> dict:
    """Lift a 20-key sibling into a comparable instance fingerprint source."""
    sched = row.get("protocol_binding", {}).get("schedule") or ["consult"]
    return {
        "id": row["id"],
        "name": row.get("name"),
        "roles": list(row.get("roles") or []),
        "protocol_schedule": list(sched) if not isinstance(sched, str) else [sched],
        "protocol_binding": row.get("protocol_binding") or {"schedule": sched},
        "voting": row.get("voting") or {},
        "stopping": row.get("stopping") or {},
        "binding": row.get("default_binding") or "static",
        "default_binding": row.get("default_binding") or "static",
        "integrity": row.get("integrity") or {"explanation_required": False},
        "meta": row.get("meta") or {},
        "purpose_class": (row.get("meta") or {}).get("purpose_class"),
        "explanation": [],
        "overrides": [],
    }


def nearest_sibling(instance: dict, siblings: list[dict]) -> dict:
    scored = []
    for raw in siblings:
        sib = preset_from_static_sibling(raw) if "protocol_schedule" not in raw else raw
        d = distance(instance, sib)
        scored.append(
            {
                "id": sib.get("id"),
                "distance": d,
                "sort": (
                    d["integer_axes"],
                    d["role_jaccard_distance"],
                    str(sib.get("id")),
                ),
            }
        )
    scored.sort(key=lambda r: r["sort"])
    if not scored:
        raise ComposerError("no siblings")
    winner = scored[0]
    return {
        "nearest_id": winner["id"],
        "distance": winner["distance"],
        "ranked": scored,
    }
