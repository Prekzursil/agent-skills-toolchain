"""Executable egress policy-as-code (IMP-0244). CI evaluates emit(), not prose."""
from __future__ import annotations

from typing import Any

POLICY_ID = "wf.policy-as-code.egress-undeclared-pii"
PROGRAM_KIND = "policy-program"
SOURCE_POLICY = {
    "policy_id": POLICY_ID,
    "version": 1,
    "description": "Source form of the executable egress policy.",
    "rules": [
        {
            "id": "no-undeclared-pii",
            "op": "subset",
            "left": ["egress", "payload_fields"],
            "right": ["declared", "pii_fields"],
        },
        {
            "id": "destinations-allowlist",
            "op": "subset",
            "left": ["egress", "destinations"],
            "right": ["declared", "destinations"],
        },
    ],
}


class PolicyNotExecutable(ValueError):
    """Prose or unstructured policy cannot be emitted as an executable program."""


def _lookup(doc: dict[str, Any], path: list[str]) -> Any:
    cur: Any = doc
    for key in path:
        if not isinstance(cur, dict):
            return []
        cur = cur.get(key)
    return cur if cur is not None else []


def emit(source: Any) -> dict[str, Any]:
    if isinstance(source, str):
        text = source.strip()
        if text.startswith("{") or text.startswith("["):
            import json

            source = json.loads(text)
        else:
            raise PolicyNotExecutable("prose-only policy is not executable")
    if not isinstance(source, dict) or not source.get("rules"):
        raise PolicyNotExecutable("policy source has no executable rules")
    ops = []
    for rule in source["rules"]:
        if not isinstance(rule, dict):
            continue
        ops.append(
            {
                "id": str(rule.get("id") or "rule"),
                "op": str(rule.get("op") or "subset"),
                "left": list(rule.get("left") or []),
                "right": list(rule.get("right") or []),
            }
        )
    if len(ops) < 2:
        raise PolicyNotExecutable("emitted program is thinner than two rules")
    return {
        "kind": PROGRAM_KIND,
        "policy_id": str(source.get("policy_id") or POLICY_ID),
        "ops": ops,
        "prose_consulted": False,
    }


def emit_default() -> dict[str, Any]:
    return emit(SOURCE_POLICY)


def evaluate_program(program: dict[str, Any], subject: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    for op in program.get("ops") or []:
        left = _lookup(subject, list(op.get("left") or []))
        right = _lookup(subject, list(op.get("right") or []))
        left_s = {str(x) for x in (left if isinstance(left, list) else [left])}
        right_s = {str(x) for x in (right if isinstance(right, list) else [right])}
        extra = sorted(left_s - right_s)
        if extra:
            violations.append({"op": op.get("id"), "extra": extra})
    decision = "FAIL" if violations else "PASS"
    return {
        "decision": decision,
        "violations": violations,
        "prose_consulted": False,
        "policy_id": program.get("policy_id") or POLICY_ID,
    }
