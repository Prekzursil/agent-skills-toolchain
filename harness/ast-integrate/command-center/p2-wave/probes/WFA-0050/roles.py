"""Council role vocabulary reconstructed from on-disk CNL artifacts.

11-COUNCIL-SPECIFICATION.md is not on this worktree. Canonical ids below are
read from CNL-0105, CNL-0114 and CNL-0033. Unmapped names become explicit
extensions; they are never force-fitted.
"""
from __future__ import annotations

CANONICAL = {
    "chair": {
        "source": "command-center/p2-wave/probes/CNL-0114/family.py chair/procedure-only; CNL-0105 template chair",
    },
    "editor": {
        "source": "command-center/design/council/CNL-0105-anonymous-peer-review-preset-with-an-author-rebuttal-round.md roles.editor",
    },
    "author": {
        "source": "CNL-0105 roles.author",
    },
    "reviewer": {
        "source": "CNL-0105 roles.reviewer-1/2/3",
    },
    "critic": {
        "source": "WORK-UNIT-CATALOG.json IMP-0165 (critic / red team / refuter comparable)",
    },
    "red": {
        "source": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
    },
    "blue": {
        "source": "CNL-0033 blue coverage-obligation",
    },
    "scribe": {
        "source": "CNL-0114 family.py template scribe / id recorder",
    },
    "bargainer": {
        "source": "CNL-0114 family.py template bargainer",
    },
    "mediator": {
        "source": "CNL-0114 family.py id mediator / template neutral-reframer",
    },
    "advocate": {
        "source": "CNL-0114 family.py id advocate.A / template hypothesis-holder",
    },
    "stakeholder-decider": {
        "source": "CNL-0114 family.py template stakeholder-decider",
    },
}

SYNONYMS = {
    "chair": "chair",
    "manager": "chair",
    "groupchatmanager": "chair",
    "group-chat-manager": "chair",
    "editor": "editor",
    "author": "author",
    "user": "author",
    "userproxy": "author",
    "user-proxy": "author",
    "reviewer": "reviewer",
    "critic": "critic",
    "refuter": "critic",
    "red": "red",
    "red-team": "red",
    "blue": "blue",
    "defender": "blue",
    "scribe": "scribe",
    "recorder": "scribe",
    "mediator": "mediator",
    "advocate": "advocate",
}


def _norm(name: str) -> str:
    return name.strip().lower().replace("_", "-").replace(" ", "-")


def map_role(name: str, *, hints: dict | None = None) -> dict:
    """Map a framework role onto the council vocabulary or explicitly extend it."""
    hints = hints or {}
    key = _norm(name)
    if hints.get("human_input_mode") == "NEVER" and key in {"user", "userproxy", "user-proxy"}:
        return {
            "source_name": name,
            "status": "EXTEND",
            "council_id": None,
            "extension_id": "user-proxy-never",
            "reason": (
                "UserProxyAgent with human_input_mode=NEVER is not a human author "
                "seat; it is an automated proxy. Declared extension, not force-fitted."
            ),
        }
    if key in SYNONYMS:
        cid = SYNONYMS[key]
        return {
            "source_name": name,
            "status": "MAPPED",
            "council_id": cid,
            "extension_id": None,
            "reason": f"synonym {key} -> {cid} ({CANONICAL[cid]['source']})",
        }
    if hints.get("kind") == "crew-job-title":
        return {
            "source_name": name,
            "status": "EXTEND",
            "council_id": None,
            "extension_id": "crew-job-title",
            "reason": (
                "CrewAI Agent.role is a free-form job title, not a council seat. "
                "Explicit vocabulary extension crew-job-title."
            ),
        }
    return {
        "source_name": name,
        "status": "EXTEND",
        "council_id": None,
        "extension_id": "specialist",
        "reason": (
            f"{name!r} is not in the on-disk council vocabulary; "
            "explicit extension specialist (UNKNOWN would also be honest; "
            "specialist records the AutoGen assistant/worker job)."
        ),
    }
