"""Unknown-field policy flag for ARC-0100.

The flag, not schema additionalProperties, is the source of truth:

  REJECT  extra keys are a named unknown-field failure (forward-incompat
          for a strict consumer; producer-side lint for frozen manifests)
  IGNORE  extra keys are stripped, then remaining known fields are typed

A missing required field or a wrong type is schema/syntax, never unknown-field.
That split is the anti-tautology: a rejecting fixture that fails for the wrong
reason does not count as the unknown-field test.
"""
from __future__ import annotations

from typing import Any

from jsonschema import Draft7Validator

POLICIES = ("REJECT", "IGNORE")
FUTURE_FIELD = "future_optional_field"
META_KEYS = ("$schema", "$id")


class Verdict:
    __slots__ = ("accepted", "reason", "reason_kind", "extras", "policy")

    def __init__(
        self,
        accepted: bool,
        reason: str,
        reason_kind: str,
        extras: list[str],
        policy: str,
    ) -> None:
        self.accepted = accepted
        self.reason = reason
        self.reason_kind = reason_kind
        self.extras = extras
        self.policy = policy

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "reason": self.reason,
            "reason_kind": self.reason_kind,
            "extras": list(self.extras),
            "policy": self.policy,
        }


def unknown_keys(instance: Any, schema: dict) -> list[str]:
    if not isinstance(instance, dict):
        return []
    known = set(schema.get("properties") or {})
    extras = [
        k
        for k in instance
        if k not in known and k not in META_KEYS
    ]
    return sorted(extras)


def validate(
    instance: Any,
    schema: dict,
    unknown_field_policy: str,
) -> Verdict:
    policy = str(unknown_field_policy or "").upper()
    if policy not in POLICIES:
        raise ValueError(f"unknown_field_policy must be one of {POLICIES}, got {unknown_field_policy!r}")
    if not isinstance(instance, dict):
        return Verdict(
            False,
            f"syntax:not-object:{type(instance).__name__}",
            "syntax",
            [],
            policy,
        )
    extras = unknown_keys(instance, schema)
    if policy == "REJECT" and extras:
        return Verdict(
            False,
            "unknown-field:" + ",".join(extras),
            "unknown-field",
            extras,
            policy,
        )
    to_check = instance
    if policy == "IGNORE" and extras:
        to_check = {k: v for k, v in instance.items() if k not in extras}
    schema_for_types = dict(schema)
    schema_for_types["additionalProperties"] = True
    errors = list(Draft7Validator(schema_for_types).iter_errors(to_check))
    if errors:
        err = errors[0]
        path = ".".join(str(p) for p in err.absolute_path)
        loc = f"@{path}" if path else "@/"
        return Verdict(
            False,
            f"schema:{loc}:{err.message}",
            "schema",
            extras,
            policy,
        )
    return Verdict(True, "ok", "ok", extras, policy)
