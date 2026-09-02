#!/usr/bin/env python3
"""Execute a stated window of capability invocations through invoke()."""
from __future__ import annotations

from pathlib import Path

from enforcement import (
    ENFORCEMENT_FUNCTION,
    ENFORCEMENT_MODULE,
    Permission,
    Record,
    DeclarationError,
    invoke,
    reset_seq,
    evaluate,
)
from reconcile import MIN_EXECUTIONS, reconcile

HERE = Path(__file__).resolve().parent
DATA = HERE / "fixtures" / "data"

CAPABILITIES: dict[str, dict] = {
    "cap.reader": {
        "kind": "plugin",
        "declared": [
            Permission("tool", "Read"),
            Permission("path", "data/ok.txt"),
        ],
    },
    "cap.writer": {
        "kind": "plugin",
        "declared": [
            Permission("tool", "Write"),
            Permission("path", "scratch/*"),
        ],
    },
    "cap.wide": {
        "kind": "plugin",
        "declared": [
            Permission("tool", "Read"),
            Permission("tool", "Write"),
            Permission("tool", "Bash"),
            Permission("net", "example.test"),
        ],
    },
    "cap.sneak": {
        "kind": "plugin",
        "declared": [
            Permission("tool", "Read"),
        ],
    },
    "skill.scoped": {
        "kind": "skill",
        "declared": [
            Permission("tool", "Read"),
            Permission("path", "skills/**"),
        ],
    },
    "mcp.demo": {
        "kind": "mcp",
        "declared": [
            Permission("tool", "mcp.demo/echo"),
        ],
    },
    "cap.denied-write": {
        "kind": "plugin",
        "declared": [
            Permission("tool", "Write", "grant"),
            Permission("tool", "Write", "deny"),
            Permission("path", "scratch/*"),
        ],
    },
}


def _read_ok() -> None:
    text = (DATA / "ok.txt").read_text(encoding="utf-8")
    if "ok-fixture" not in text:
        raise RuntimeError("fixture data/ok.txt missing marker")


def _write_scratch(name: str) -> None:
    path = HERE / "fixtures" / "scratch" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def _perm(cls: str, name: str) -> Permission:
    return Permission(cls, name, "grant")


def _run(actions: list[tuple[str, Permission, object]]) -> list[Record]:
    reset_seq()
    declared = {k: v["declared"] for k, v in CAPABILITIES.items()}
    kinds = {k: v["kind"] for k, v in CAPABILITIES.items()}
    records: list[Record] = []
    for cap_id, requested, effect in actions:
        records.append(
            invoke(
                cap_id,
                kinds[cap_id],
                declared[cap_id],
                requested,
                side_effect=effect if callable(effect) else None,
            )
        )
    return records


def adequate_actions() -> list[tuple[str, Permission, object]]:
    """>= MIN_EXECUTIONS real invocations, covering both directions + deny."""
    write1 = lambda: _write_scratch("a.txt")  # noqa: E731
    write2 = lambda: _write_scratch("b.txt")  # noqa: E731
    actions: list[tuple[str, Permission, object]] = [
        ("cap.reader", _perm("tool", "Read"), _read_ok),
        ("cap.reader", _perm("path", "data/ok.txt"), None),
        ("cap.reader", _perm("tool", "Read"), _read_ok),
        ("cap.reader", _perm("path", "data/ok.txt"), None),
        ("cap.writer", _perm("tool", "Write"), write1),
        ("cap.writer", _perm("path", "scratch/a.txt"), None),
        ("cap.writer", _perm("tool", "Write"), write2),
        ("cap.wide", _perm("tool", "Read"), _read_ok),
        ("cap.wide", _perm("tool", "Write"), write1),
        ("cap.sneak", _perm("tool", "Read"), _read_ok),
        ("cap.sneak", _perm("tool", "Write"), None),
        ("skill.scoped", _perm("tool", "Read"), _read_ok),
        ("skill.scoped", _perm("path", "skills/ok.md"), None),
        ("skill.scoped", _perm("path", "data/ok.txt"), None),
        ("mcp.demo", _perm("tool", "mcp.demo/echo"), None),
        ("mcp.demo", _perm("tool", "mcp.demo/secret"), None),
        ("cap.denied-write", _perm("tool", "Write"), None),
        ("cap.reader", _perm("tool", "Read"), _read_ok),
        ("cap.reader", _perm("tool", "Grep"), None),
        ("cap.wide", _perm("tool", "Read"), _read_ok),
        ("cap.writer", _perm("path", "scratch/b.txt"), None),
        ("mcp.demo", _perm("tool", "mcp.demo/echo"), None),
    ]
    if len(actions) < MIN_EXECUTIONS:
        raise RuntimeError(f"adequate window too small: {len(actions)}")
    return actions


def thin_actions() -> list[tuple[str, Permission, object]]:
    return [
        ("cap.reader", _perm("tool", "Read"), _read_ok),
        ("cap.wide", _perm("tool", "Read"), _read_ok),
        ("cap.sneak", _perm("tool", "Write"), None),
    ]


def run_window(window_id: str, actions: list[tuple[str, Permission, object]]) -> dict:
    declared = {k: v["declared"] for k, v in CAPABILITIES.items()}
    records = _run(actions)
    report = reconcile(declared, records, window_id)
    report["records"] = [
        {
            "seq": r.seq,
            "capability_id": r.capability_id,
            "permission": r.permission,
            "decision": r.decision,
            "reason": r.reason,
            "enforcement_point": r.enforcement_point,
            "kind": r.kind,
        }
        for r in records
    ]
    report["enforcement_point"] = {
        "module": ENFORCEMENT_MODULE,
        "function": ENFORCEMENT_FUNCTION,
        "rule": (
            "Deny-match wins; else grant-match ALLOW; else DENY undeclared. "
            "Side effects run only inside invoke() after ALLOW. "
            "Wildcard credential grants are rejected at validation, not evaluation."
        ),
    }
    return report


def run_adequate() -> dict:
    return run_window("fixture-adequate", adequate_actions())


def run_thin() -> dict:
    return run_window("fixture-thin", thin_actions())


def delivering_agent_window() -> dict:
    """This worker has no harness execution trace. Honest NOT-CHECKED."""
    return {
        "window_id": "delivering-agent",
        "sample_size": 0,
        "min_executions": MIN_EXECUTIONS,
        "adequacy": "NO-RECORDS",
        "sample_adequate": False,
        "declared_not_observed": [],
        "observed_not_declared": [],
        "exercised_and_declared": [],
        "deny_count": 0,
        "allow_count": 0,
        "enforcement_points": [],
        "verdict_shape": "two-directions",
        "why_not_checked": (
            "No harness execution log for the delivering agent. A permission "
            "that is simply never seen is not judged OVER-GRANT. Fixture "
            "windows below are the measured object."
        ),
        "records": [],
    }


def credential_wildcard_rejected() -> bool:
    try:
        evaluate(
            [Permission("credential", "*", "grant")],
            Permission("credential", "api-key", "grant"),
        )
    except DeclarationError as exc:
        return "wildcard credential" in str(exc)
    return False


def both_states_enforcement() -> dict:
    """Authorized Write is silent; undeclared Write fires DENY."""
    allow = evaluate(
        CAPABILITIES["cap.writer"]["declared"],
        Permission("tool", "Write"),
    )
    deny = evaluate(
        CAPABILITIES["cap.sneak"]["declared"],
        Permission("tool", "Write"),
    )
    deny_rule = evaluate(
        CAPABILITIES["cap.denied-write"]["declared"],
        Permission("tool", "Write"),
    )
    return {
        "authorized_write": allow.verdict,
        "authorized_reason": allow.reason,
        "undeclared_write": deny.verdict,
        "undeclared_reason": deny.reason,
        "deny_rule_write": deny_rule.verdict,
        "deny_rule_reason": deny_rule.reason,
        "fires_on_under_declaration": deny.verdict == "DENY"
        and deny.reason == "undeclared",
        "silent_on_grant": allow.verdict == "ALLOW",
        "deny_wins": deny_rule.verdict == "DENY" and deny_rule.reason == "deny-rule",
    }
