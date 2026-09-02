"""Planted casts and specs for TST-0264 minimum-deliberation probes."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

ROLES = ("advocate", "skeptic", "synthesizer")
PERMISSIVE_STOP = "true"

PREMATURE_SPEC = {
    "id": "tst-0264-premature-stop",
    "roles": list(ROLES),
    "mandated_roles": list(ROLES),
    "stopping_expression": PERMISSIVE_STOP,
    "min_rounds": 1,
    "min_independent_briefs": 1,
    "min_evidence": 1,
    "max_rounds": 4,
}

HEALTHY_SPEC = {
    "id": "tst-0264-floors-met",
    "roles": list(ROLES),
    "mandated_roles": list(ROLES),
    "stopping_expression": PERMISSIVE_STOP,
    "min_rounds": 2,
    "min_independent_briefs": 3,
    "min_evidence": 3,
    "max_rounds": 6,
}

FALSE_STOP_SPEC = {
    **HEALTHY_SPEC,
    "id": "tst-0264-expression-false",
    "stopping_expression": "false",
}

BYPASS_SPEC = {
    **PREMATURE_SPEC,
    "id": "tst-0264-bypass-min-rounds",
    "min_rounds": 0,
}


def silent_cast() -> list[dict]:
    """Round-1 (and later) silence: no opening briefs, no evidence, no speech."""
    return [{"id": role, "role": role, "script": []} for role in ROLES]


def productive_cast() -> list[dict]:
    """Each mandated role files a distinct opening brief + evidence, then speaks again."""
    briefs = {
        "advocate": "Ship behind a feature flag and measure rollback cost.",
        "skeptic": "The flag does not bound blast radius if defaults stay on.",
        "synthesizer": "Require default-off plus an executable rollback drill.",
    }
    evidence = {
        "advocate": "cite:incident-2026-03-rollback-runbook",
        "skeptic": "cite:postmortem-default-on-flag-leak",
        "synthesizer": "cite:drill-log-rollback-under-5-min",
    }
    cast = []
    for role in ROLES:
        cast.append(
            {
                "id": role,
                "role": role,
                "script": [
                    {
                        "round": 1,
                        "kind": "opening_brief",
                        "text": briefs[role],
                    },
                    {
                        "round": 1,
                        "kind": "evidence",
                        "citation": evidence[role],
                        "text": evidence[role],
                    },
                    {
                        "round": 2,
                        "kind": "speech",
                        "text": f"{role} restates their independent position with no new claim.",
                    },
                ],
            }
        )
    return cast


def spec(template: dict) -> dict:
    return deepcopy(template)
