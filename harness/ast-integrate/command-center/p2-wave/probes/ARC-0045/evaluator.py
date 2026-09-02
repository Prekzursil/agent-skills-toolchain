#!/usr/bin/env python3
"""A7 single permission choke.

Every capability invocation that this architecture admits must call
`evaluate()` before any side effect. No other function may mint a GRANT.
Default is DENY. Deny overrides grant. Least-privilege grants are named;
`*` is rejected at declaration time, not evaluated as a wildcard grant.
"""
from __future__ import annotations

from typing import Any, Mapping

CHOKE_ID = "a7.permission.evaluate"
CHOKE_MODULE = "command-center/p2-wave/probes/ARC-0045/evaluator.py"
RESOURCE_CLASSES = (
    "tool",
    "path",
    "egress",
    "subprocess",
    "credential",
    "install",
    "activate",
    "dispatch",
    "workflow",
    "council",
    "mcp",
)
EFFECTS = ("GRANT", "DENY")
WILDCARD_CHARS = frozenset("*?")


class InvalidGrantSet(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(errors[0] if errors else "invalid grant set")


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def declaration_errors(grants: Any) -> list[str]:
    """Fail closed at declaration, before evaluate()."""
    errors: list[str] = []
    if not isinstance(grants, list):
        return ["grants must be a list"]
    seen: set[tuple[str, str, str, str]] = set()
    for i, row in enumerate(grants):
        loc = f"grants[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{loc} must be an object")
            continue
        effect = _str(row.get("effect"))
        cls = _str(row.get("class"))
        action = _str(row.get("action"))
        selector = _str(row.get("selector"))
        if effect not in {"grant", "deny"}:
            errors.append(f"{loc}.effect must be grant|deny")
        if cls not in RESOURCE_CLASSES:
            errors.append(f"{loc}.class is not a known resource class")
        if not action:
            errors.append(f"{loc}.action is required")
        elif action == "*" or any(ch in action for ch in WILDCARD_CHARS):
            errors.append(f"{loc}.action wildcards are forbidden")
        if not selector:
            errors.append(f"{loc}.selector is required")
        else:
            if selector == "*" or selector == "**":
                errors.append(f"{loc}.selector may not be a bare wildcard")
            if cls == "credential" and any(ch in selector for ch in WILDCARD_CHARS):
                errors.append(f"{loc} credential selectors may not contain wildcards")
            if row.get("skip_evaluator") or row.get("trusted_publisher"):
                errors.append(f"{loc} trusted-publisher / skip_evaluator is inexpressible")
        key = (effect or "", cls or "", action or "", selector or "")
        if key in seen:
            errors.append(f"{loc} duplicates {key}")
        seen.add(key)
    return errors


def validate_grants(grants: Any) -> list[dict[str, str]]:
    errors = declaration_errors(grants)
    if errors:
        raise InvalidGrantSet(errors)
    return list(grants)


def _selector_match(pattern: str, value: str, cls: str) -> bool:
    if pattern == value:
        return True
    # Path prefix with trailing /** is the only glob admitted, and only for path.
    if cls == "path" and pattern.endswith("/**"):
        prefix = pattern[:-3]
        return value == prefix or value.startswith(prefix + "/")
    return False


def evaluate(invocation: Mapping[str, Any], grants: Any) -> dict[str, Any]:
    """THE choke. Side-effecting dispatch may proceed only on GRANT from here."""
    grants = validate_grants(grants)
    subject = _str(invocation.get("subject"))
    cls = _str(invocation.get("class"))
    action = _str(invocation.get("action"))
    selector = _str(invocation.get("selector"))
    if not subject or cls not in RESOURCE_CLASSES or not action or not selector:
        return {
            "effect": "DENY",
            "reason": "malformed-invocation",
            "choke_id": CHOKE_ID,
            "matched_grants": [],
            "matched_denies": [],
        }
    if invocation.get("skip_evaluator") or invocation.get("trusted_publisher_bypass"):
        return {
            "effect": "DENY",
            "reason": "inexpressible-skip-choke",
            "choke_id": CHOKE_ID,
            "matched_grants": [],
            "matched_denies": [],
        }
    matched_g: list[dict[str, str]] = []
    matched_d: list[dict[str, str]] = []
    for row in grants:
        if row.get("class") != cls:
            continue
        if row.get("action") != action:
            continue
        if not _selector_match(str(row.get("selector")), selector, cls):
            continue
        if row.get("effect") == "deny":
            matched_d.append(row)
        elif row.get("effect") == "grant":
            matched_g.append(row)
    if matched_d:
        return {
            "effect": "DENY",
            "reason": "deny-overrides",
            "choke_id": CHOKE_ID,
            "matched_grants": matched_g,
            "matched_denies": matched_d,
        }
    if not matched_g:
        return {
            "effect": "DENY",
            "reason": "closed-world-default",
            "choke_id": CHOKE_ID,
            "matched_grants": [],
            "matched_denies": [],
        }
    provenance = invocation.get("provenance")
    if not isinstance(provenance, dict) or not _str(provenance.get("digest")):
        return {
            "effect": "DENY",
            "reason": "missing-provenance",
            "choke_id": CHOKE_ID,
            "matched_grants": matched_g,
            "matched_denies": [],
        }
    if provenance.get("ok") is not True:
        return {
            "effect": "DENY",
            "reason": "provenance-rejected",
            "choke_id": CHOKE_ID,
            "matched_grants": matched_g,
            "matched_denies": [],
        }
    bundle = invocation.get("bundle")
    if isinstance(bundle, dict) and bundle.get("secret_free") is not True:
        return {
            "effect": "DENY",
            "reason": "secret-bearing-bundle",
            "choke_id": CHOKE_ID,
            "matched_grants": matched_g,
            "matched_denies": [],
        }
    return {
        "effect": "GRANT",
        "reason": "named-grant",
        "choke_id": CHOKE_ID,
        "matched_grants": matched_g,
        "matched_denies": [],
    }


def require_grant(invocation: Mapping[str, Any], grants: Any) -> dict[str, Any]:
    decision = evaluate(invocation, grants)
    if decision["effect"] != "GRANT":
        raise PermissionError(decision["reason"])
    return decision
