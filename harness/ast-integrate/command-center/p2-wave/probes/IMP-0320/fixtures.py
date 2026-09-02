"""Recorded councils for IMP-0320.

Collapsed: four seats, one model, four role *labels* and four role *prompts*,
but the outputs are near-paraphrases of one cache recommendation with no role
markers. That is the planted pathology.

Diverse: four seats, four models, four role-shaped outputs with distinct
markers and distinct claims.

Hard case: four seats, ONE model, strong role prompts, and the outputs
actually follow those roles (distinct claims + role markers). Same-model is
not treated as collapse. Classification is whatever the detector returns;
thresholds were not moved to force a FIRE.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

COLLAPSED_CORE = (
    "cache session reads in redis in front of the store to cut load and keep "
    "the charge path unchanged"
)

ROLES = ("advocate", "skeptic", "domain_expert", "user_proxy")


def _seat(seat_id: str, role: str, model: str, prompt: str, output: str) -> dict[str, Any]:
    return {
        "seat_id": seat_id,
        "role": role,
        "model": model,
        "role_prompt": prompt,
        "output": output,
    }


def collapsed_council() -> dict[str, Any]:
    """Same model, different role prompts, near-identical outputs. Must FIRE."""
    variants = [
        COLLAPSED_CORE,
        COLLAPSED_CORE + " today",
        COLLAPSED_CORE.replace("and keep", ", keeping"),
        COLLAPSED_CORE + " now",
    ]
    prompts = [
        "Advocate: argue for shipping the Redis cache; use recommend/ship/benefit language.",
        "Skeptic: hunt failure modes and untested claims; use refute/stampede language.",
        "Domain expert: bind the choice to schema and measured p99 latency constraints.",
        "User proxy: demand an operator runbook, pager path, and rollback toggle.",
    ]
    seats = [
        _seat(f"c{i+1}", ROLES[i], "claude-opus-same", prompts[i], variants[i])
        for i in range(4)
    ]
    return {
        "id": "collapsed-same-model-role-prompts",
        "kind": "collapsed",
        "note": (
            "Role prompts differ; outputs do not. Detector must use outputs, "
            "not declared roles or prompt text."
        ),
        "seats": seats,
    }


def diverse_council() -> dict[str, Any]:
    """Genuinely different models and role-shaped outputs. Must be SILENT."""
    outputs = {
        "advocate": (
            "I recommend we ship the Redis cache: the benefit is lower store "
            "load and the opportunity to adopt a cheaper read path without "
            "blocking charges."
        ),
        "skeptic": (
            "I refute the free-lunch claim. The untested failure is a cache "
            "stampede on TTL expiry; that risk needs a counterexample under "
            "burst traffic before we call it safe."
        ),
        "domain_expert": (
            "The schema of the session blob plus the measured p99 latency "
            "invariant is the constraint; Redis only helps if the key layout "
            "matches that latency budget."
        ),
        "user_proxy": (
            "The operator oncall needs a runbook and a one-toggle rollback "
            "before this hits the pager at 3am."
        ),
    }
    models = {
        "advocate": "opus-advocate-lab",
        "skeptic": "sonnet-skeptic-lab",
        "domain_expert": "haiku-expert-lab",
        "user_proxy": "gpt-user-proxy-lab",
    }
    prompts = {
        "advocate": "You are advocate. Stress ship/benefit/opportunity.",
        "skeptic": "You are skeptic. Stress refute/failure/stampede.",
        "domain_expert": "You are domain expert. Stress schema/measured/p99.",
        "user_proxy": "You are user proxy. Stress operator/oncall/rollback.",
    }
    seats = [
        _seat(f"d{i+1}", role, models[role], prompts[role], outputs[role])
        for i, role in enumerate(ROLES)
    ]
    return {
        "id": "diverse-distinct-models-and-roles",
        "kind": "diverse",
        "note": "Distinct models, distinct claims, role markers present.",
        "seats": seats,
    }


def hard_same_model_strong_roles() -> dict[str, Any]:
    """Single model, strong role prompts, differentiated outputs.

    Catalog negative control: report classification honestly. Do not retune
    SIM_FIRE/VOCAB_FIRE until this FIRE/SILENT matches a preferred story.
    """
    base = diverse_council()
    hard = deepcopy(base)
    hard["id"] = "hard-same-model-strong-role-prompts"
    hard["kind"] = "hard-same-model"
    hard["note"] = (
        "Every seat uses model claude-opus-same. Role prompts are strong and "
        "the outputs keep role markers. Same-model is not a fire rule."
    )
    for seat in hard["seats"]:
        seat["model"] = "claude-opus-same"
        seat["role_prompt"] = (
            f"STRONG ROLE={seat['role']}. Stay in voice. Use that role's "
            f"markers. Do not copy other seats."
        )
    return hard


def all_councils() -> dict[str, dict[str, Any]]:
    return {
        "collapsed": collapsed_council(),
        "diverse": diverse_council(),
        "hard": hard_same_model_strong_roles(),
    }
