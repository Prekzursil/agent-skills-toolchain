"""Published selector tables for CNL-0013.

A reviewer with this module (or the copy embedded in an explanation record)
can recompute every dial without calling selector.select().
Protocol ids are the catalog names from WORK-UNIT-CATALOG.json CNL-0038..CNL-0046.
Default four voices match command-center/p2-wave/probes/ARC-0010/registry.json
skill.council roles. Risk-tier enum is local to this unit (CNL-0003 not delivered).
"""
from __future__ import annotations

DIALS = ("protocol", "voting_method", "stopping_rule", "roles")

DEFAULTS = {
    "protocol": "P01-free-form-moderated-panel",
    "voting_method": "majority",
    "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
    "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
}

# First matching keyword rule wins. Keywords are case-insensitive substrings.
TASK_CLASS_RULES = [
    {
        "id": "TC-incident",
        "class": "incident",
        "any_keywords": [
            "secret leak",
            "production",
            "ci logs",
            "contain the token",
            "outage",
            "sev-",
            "incident",
        ],
        "prose": "incident-response language routes to the incident class",
    },
    {
        "id": "TC-safety",
        "class": "safety",
        "any_keywords": [
            "safety interlock",
            "disable the safety",
            "two-key stop",
        ],
        "prose": "safety-interlock language routes to the safety class",
    },
    {
        "id": "TC-irreversible",
        "class": "irreversible",
        "any_keywords": [
            "budget ceiling",
            "irreversible",
            "unattended councils",
            "10x",
        ],
        "prose": "irreversible-spend language routes to the irreversible class",
    },
    {
        "id": "TC-judicial",
        "class": "judicial",
        "any_keywords": [
            "adjudicate",
            "silent-loss",
            "hand edit",
            "verdict",
        ],
        "prose": "adjudication language routes to the judicial class",
    },
    {
        "id": "TC-design",
        "class": "design",
        "any_keywords": [
            "control-plane",
            "load-order",
            "file set",
            "architecture",
            "before freeze",
        ],
        "prose": "design-review language routes to the design class",
    },
    {
        "id": "TC-adversarial",
        "class": "adversarial",
        "any_keywords": [
            "red-team",
            "silent default",
            "hide an override",
            "attack",
        ],
        "prose": "red-team language routes to the adversarial class",
    },
    {
        "id": "TC-generative",
        "class": "generative",
        "any_keywords": [
            "brainstorm",
            "names for",
            "idea count",
        ],
        "prose": "brainstorm language routes to the generative class",
    },
    {
        "id": "TC-forecast",
        "class": "forecast",
        "any_keywords": [
            "estimate hours",
            "forecast",
            "prediction",
        ],
        "prose": "estimation language routes to the forecast class",
    },
    {
        "id": "TC-tradecraft",
        "class": "tradecraft",
        "any_keywords": [
            "key assumption",
            "premortem",
            "competing hypothes",
        ],
        "prose": "structured-analytic language routes to the tradecraft class",
    },
    {
        "id": "TC-general",
        "class": "general",
        "any_keywords": [],
        "prose": "fallback class when no specialist keyword matched",
        "fallback": True,
    },
]

RISK_BASE = {
    "T0": {
        "id": "RISK-T0",
        "prose": "T0 informational work uses a two-seat panel and a short majority stop",
        "dials": {
            "protocol": "P01-free-form-moderated-panel",
            "voting_method": "majority",
            "stopping_rule": "stop_if(max_rounds>=2 OR majority_reached)",
            "roles": ["Architect", "Pragmatist"],
        },
    },
    "T1": {
        "id": "RISK-T1",
        "prose": "T1 low-risk work keeps the four-voice default panel",
        "dials": {
            "protocol": "P01-free-form-moderated-panel",
            "voting_method": "majority",
            "stopping_rule": "stop_if(max_rounds>=3 OR majority_reached)",
            "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
        },
    },
    "T2": {
        "id": "RISK-T2",
        "prose": "T2 material work adds a moderator, supermajority, and an objection-clear stop",
        "dials": {
            "protocol": "P45-scientific-peer-review",
            "voting_method": "supermajority-2/3",
            "stopping_rule": "stop_if((max_rounds>=5 AND unresolved_objections==0) OR max_rounds>=8)",
            "roles": ["Architect", "Skeptic", "Pragmatist", "Critic", "Moderator"],
        },
    },
    "T3": {
        "id": "RISK-T3",
        "prose": "T3 high-stakes work mandates a devil's advocate, two-key vote, and cited claims",
        "dials": {
            "protocol": "P10-mandated-devils-advocate",
            "voting_method": "two-key",
            "stopping_rule": "stop_if((max_rounds>=8 AND two_key_agree AND every_claim_has_citation) OR owner_halt)",
            "roles": [
                "Architect",
                "Skeptic",
                "Pragmatist",
                "Critic",
                "Moderator",
                "DevilsAdvocate",
                "EvidenceClerk",
            ],
        },
    },
    "T4": {
        "id": "RISK-T4",
        "prose": "T4 irreversible work never auto-stops: the owner must ratify stepwise",
        "dials": {
            "protocol": "P58-owner-in-the-loop-stepwise",
            "voting_method": "owner-ratify",
            "stopping_rule": "stop_if(owner_explicit_accept); never auto-stop on consensus",
            "roles": [
                "Architect",
                "Skeptic",
                "Pragmatist",
                "Critic",
                "Moderator",
                "DevilsAdvocate",
                "EvidenceClerk",
                "Owner",
            ],
        },
    },
}

# Overlays replace named dials; roles_add appends unique seats.
CLASS_OVERLAY = {
    ("T1", "generative"): {
        "id": "CLASS-T1-generative",
        "prose": "T1 generative work uses the brainstorming swarm and an ideator seat",
        "dials": {
            "protocol": "P26-brainstorming-swarm",
            "voting_method": "approval",
        },
        "roles_add": ["Ideator"],
    },
    ("T2", "design"): {
        "id": "CLASS-T2-design",
        "prose": "T2 design work uses the architecture-review-board protocol",
        "dials": {"protocol": "P46-architecture-review-board"},
        "roles_add": [],
    },
    ("T2", "adversarial"): {
        "id": "CLASS-T2-adversarial",
        "prose": "T2 adversarial work uses mandated devil's advocate",
        "dials": {"protocol": "P10-mandated-devils-advocate"},
        "roles_add": ["DevilsAdvocate"],
    },
    ("T2", "forecast"): {
        "id": "CLASS-T2-forecast",
        "prose": "T2 forecast work uses a prediction tournament and score-then-resolve",
        "dials": {
            "protocol": "P33-prediction-tournament",
            "voting_method": "score-then-resolve",
        },
        "roles_add": [],
    },
    ("T3", "judicial"): {
        "id": "CLASS-T3-judicial",
        "prose": "T3 judicial work uses judge-and-jury rather than a debate panel",
        "dials": {"protocol": "P14-judge-and-jury"},
        "roles_add": [],
    },
    ("T3", "incident"): {
        "id": "CLASS-T3-incident",
        "prose": "T3 incident work uses the incident-war-room and a containment stop",
        "dials": {
            "protocol": "P47-incident-war-room",
            "stopping_rule": "stop_if((containment_declared AND max_rounds>=6) OR owner_halt)",
        },
        "roles_add": [],
    },
    ("T3", "tradecraft"): {
        "id": "CLASS-T3-tradecraft",
        "prose": "T3 tradecraft work uses the key-assumptions-check protocol",
        "dials": {"protocol": "P39-key-assumptions-check"},
        "roles_add": [],
    },
    ("T4", "safety"): {
        "id": "CLASS-T4-safety",
        "prose": "T4 safety-interlock work adds two-key dual-control and a safety officer",
        "dials": {"protocol": "P18-two-key-dual-control"},
        "roles_add": ["SafetyOfficer"],
    },
}

FIXTURES = [
    {
        "id": "F01",
        "risk_tier": "T0",
        "task_description": "Summarize yesterday's changelog for the internal notes wiki.",
    },
    {
        "id": "F02",
        "risk_tier": "T0",
        "task_description": "Reformat this three-column table as Markdown for the weekly brief.",
    },
    {
        "id": "F03",
        "risk_tier": "T1",
        "task_description": "Brainstorm names for a new CLI flag that dumps the selector explanation.",
    },
    {
        "id": "F04",
        "risk_tier": "T1",
        "task_description": "Review the README for typos and broken links only.",
    },
    {
        "id": "F05",
        "risk_tier": "T2",
        "task_description": "Review the A1 control-plane file set for load-order bugs before freeze.",
    },
    {
        "id": "F06",
        "risk_tier": "T2",
        "task_description": "Red-team the auto-composer so a silent default cannot hide an override.",
    },
    {
        "id": "F07",
        "risk_tier": "T3",
        "task_description": "Adjudicate whether hatch capture-back is a silent-loss of a hand edit.",
    },
    {
        "id": "F08",
        "risk_tier": "T3",
        "task_description": "Triage a production secret leak in CI logs and contain the token.",
    },
    {
        "id": "F09",
        "risk_tier": "T4",
        "task_description": "Raise the owner token budget ceiling by 10x for unattended councils.",
    },
    {
        "id": "F10",
        "risk_tier": "T4",
        "task_description": "Disable the safety interlock that blocks owner-override of two-key stop.",
    },
]


def rule_table() -> dict:
    """JSON-serialisable snapshot a reviewer can apply without this module."""
    overlays = []
    for (tier, cls), spec in CLASS_OVERLAY.items():
        overlays.append(
            {
                "risk_tier": tier,
                "task_class": cls,
                "id": spec["id"],
                "prose": spec["prose"],
                "dials": spec["dials"],
                "roles_add": list(spec.get("roles_add") or []),
            }
        )
    return {
        "dials": list(DIALS),
        "defaults": {
            "protocol": DEFAULTS["protocol"],
            "voting_method": DEFAULTS["voting_method"],
            "stopping_rule": DEFAULTS["stopping_rule"],
            "roles": list(DEFAULTS["roles"]),
        },
        "task_class_rules": TASK_CLASS_RULES,
        "risk_base": RISK_BASE,
        "class_overlays": overlays,
    }
