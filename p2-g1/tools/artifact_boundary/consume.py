"""Typed handoff consumer. apply_policy receives the policy, never a payload."""
from __future__ import annotations

from typing import Any

from artifact_boundary.corpus import Artifact
from artifact_boundary.policy import TrustedPolicy


def wrap_artifact(item: Artifact) -> dict[str, Any]:
    return {
        "kind": item.kind,
        "trusted": bool(item.trusted),
        "score": int(item.score),
        "body_chars": len(item.body or ""),
        "sha_prefix": str(abs(hash(item.body)))[:12],
    }


def unwrap_payload(env: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": env.get("kind"),
        "trusted": env.get("trusted"),
        "score": env.get("score"),
    }


def extract_facts(unwrapped: dict[str, Any]) -> list:
    facts = [["kind", unwrapped.get("kind")], ["score", str(unwrapped.get("score"))]]
    return facts


def apply_policy(policy: TrustedPolicy) -> dict[str, Any]:
    actions = ["summarise"]
    if policy.allow_credential_read:
        actions.append("credential_read")
    return {
        "verdict": policy.default_verdict,
        "role": policy.role,
        "actions": actions,
        "policy": policy.name,
    }


def consume_stage(artifacts, policy):
    wrapped = [wrap_artifact(item) for item in artifacts]
    facts = []
    for env in wrapped:
        facts.extend(extract_facts(unwrap_payload(env)))
    rec = apply_policy(policy)
    rec["facts"] = facts
    rec["wrapped_n"] = len(wrapped)
    return rec


def behavior_of(artifacts, policy) -> dict[str, Any]:
    return consume_stage(artifacts, policy)
