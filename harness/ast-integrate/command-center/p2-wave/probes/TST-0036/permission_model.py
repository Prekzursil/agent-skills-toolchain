"""Executable permission-model oracle for TST-0036.

Phase-4 permission contract as a conformance oracle, written before
IMP-0059-style runtime enforcement is broadly implemented. Every
capability class is evaluated at a single locus. An undeclared request
is DENIED and logged; a silent grant is a P0.

Capability vocabulary follows ARC-0081: tool_call, file_path,
network_egress, subprocess, credential_read.
"""
from __future__ import annotations

import fnmatch
import os
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

CAPABILITY_CLASSES = (
    "tool_call",
    "file_path",
    "network_egress",
    "subprocess",
    "credential_read",
)

ALLOW = "ALLOW"
DENY = "DENY"

WILDCARD_CREDENTIAL_READ = "rejected-at-validation"
EVALUATION_LOCUS = "single-evaluator"


@dataclass
class Rule:
    capability_class: str
    pattern: str
    effect: str  # grant | deny

    def matches(self, capability_class: str, name: str) -> bool:
        if self.capability_class != capability_class:
            return False
        return fnmatch.fnmatchcase(name, self.pattern)


@dataclass
class Policy:
    component_id: str
    evaluation_locus: str
    grants: list[Rule]
    denies: list[Rule]
    wildcard_credential_read: str
    least_privilege_statement: str


@dataclass
class AuditRecord:
    ts_ns: int
    component_id: str
    capability_class: str
    name: str
    decision: str
    reason: str
    evaluator: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ts_ns": self.ts_ns,
            "component_id": self.component_id,
            "capability_class": self.capability_class,
            "name": self.name,
            "decision": self.decision,
            "reason": self.reason,
            "evaluator": self.evaluator,
        }


@dataclass
class Decision:
    decision: str
    reason: str
    component_id: str
    capability_class: str
    name: str
    logged: bool
    record: AuditRecord | None = None


@dataclass
class SideEffectTrace:
    writes: list[str] = field(default_factory=list)
    spawns: list[list[str]] = field(default_factory=list)
    connects: list[str] = field(default_factory=list)
    credential_reads: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "writes": list(self.writes),
            "spawns": [list(s) for s in self.spawns],
            "connects": list(self.connects),
            "credential_reads": list(self.credential_reads),
        }


def _is_wildcard(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def validate_policy(policy: Policy) -> list[str]:
    errors: list[str] = []
    if policy.evaluation_locus != EVALUATION_LOCUS:
        errors.append(
            f"evaluation_locus must be {EVALUATION_LOCUS!r}, "
            f"got {policy.evaluation_locus!r}"
        )
    if policy.wildcard_credential_read != WILDCARD_CREDENTIAL_READ:
        errors.append(
            "wildcard_credential_read must be "
            f"{WILDCARD_CREDENTIAL_READ!r}"
        )
    if not policy.grants:
        errors.append("grants must contain at least one rule")
    if len(policy.least_privilege_statement) < 24:
        errors.append("least_privilege_statement too short")
    for rule in policy.grants + policy.denies:
        if rule.capability_class not in CAPABILITY_CLASSES:
            errors.append(f"unknown capability_class {rule.capability_class!r}")
        if not rule.pattern:
            errors.append("empty pattern")
        if rule.effect not in {"grant", "deny"}:
            errors.append(f"unknown effect {rule.effect!r}")
        if (
            rule.effect == "grant"
            and rule.capability_class == "credential_read"
            and _is_wildcard(rule.pattern)
        ):
            errors.append(
                "wildcard credential_read grant rejected at validation: "
                f"{rule.pattern!r}"
            )
    return errors


def validate_or_raise(policy: Policy) -> None:
    errors = validate_policy(policy)
    if errors:
        raise ValueError("; ".join(errors))


def _append_log(
    log: list[AuditRecord],
    component_id: str,
    capability_class: str,
    name: str,
    decision: str,
    reason: str,
    evaluator: str,
) -> AuditRecord:
    rec = AuditRecord(
        ts_ns=time.time_ns(),
        component_id=component_id,
        capability_class=capability_class,
        name=name,
        decision=decision,
        reason=reason,
        evaluator=evaluator,
    )
    log.append(rec)
    return rec


def evaluate_request(
    policy: Policy,
    capability_class: str,
    name: str,
    *,
    log: list[AuditRecord],
    evaluator_name: str = "reference",
) -> Decision:
    """Single evaluation locus. Deny matches beat grant matches. Default deny."""
    if capability_class not in CAPABILITY_CLASSES:
        rec = _append_log(
            log,
            policy.component_id,
            capability_class,
            name,
            DENY,
            "unknown-capability-class",
            evaluator_name,
        )
        return Decision(
            DENY, rec.reason, policy.component_id, capability_class, name, True, rec
        )

    for rule in policy.denies:
        if rule.effect == "deny" and rule.matches(capability_class, name):
            rec = _append_log(
                log,
                policy.component_id,
                capability_class,
                name,
                DENY,
                f"deny-rule:{rule.pattern}",
                evaluator_name,
            )
            return Decision(
                DENY, rec.reason, policy.component_id, capability_class, name, True, rec
            )

    for rule in policy.grants:
        if rule.effect == "grant" and rule.matches(capability_class, name):
            rec = _append_log(
                log,
                policy.component_id,
                capability_class,
                name,
                ALLOW,
                f"grant-rule:{rule.pattern}",
                evaluator_name,
            )
            return Decision(
                ALLOW, rec.reason, policy.component_id, capability_class, name, True, rec
            )

    rec = _append_log(
        log,
        policy.component_id,
        capability_class,
        name,
        DENY,
        "undeclared-permission",
        evaluator_name,
    )
    return Decision(
        DENY, rec.reason, policy.component_id, capability_class, name, True, rec
    )


Evaluator = Callable[[Policy, str, str, list[AuditRecord]], Decision]


def reference_evaluator(
    policy: Policy,
    capability_class: str,
    name: str,
    log: list[AuditRecord],
) -> Decision:
    return evaluate_request(
        policy, capability_class, name, log=log, evaluator_name="reference"
    )


def silent_grant_evaluator(
    policy: Policy,
    capability_class: str,
    name: str,
    log: list[AuditRecord],
) -> Decision:
    """P0 mutant: requests are granted with no audit record."""
    return Decision(
        ALLOW,
        "silent-grant",
        policy.component_id,
        capability_class,
        name,
        False,
        None,
    )


def deny_all_evaluator(
    policy: Policy,
    capability_class: str,
    name: str,
    log: list[AuditRecord],
) -> Decision:
    rec = _append_log(
        log,
        policy.component_id,
        capability_class,
        name,
        DENY,
        "deny-all-mutant",
        "deny-all",
    )
    return Decision(
        DENY, rec.reason, policy.component_id, capability_class, name, True, rec
    )


def grant_beats_deny_evaluator(
    policy: Policy,
    capability_class: str,
    name: str,
    log: list[AuditRecord],
) -> Decision:
    """Mutant: grant matches are checked before deny (wrong precedence)."""
    for rule in policy.grants:
        if rule.effect == "grant" and rule.matches(capability_class, name):
            rec = _append_log(
                log,
                policy.component_id,
                capability_class,
                name,
                ALLOW,
                f"grant-first:{rule.pattern}",
                "grant-beats-deny",
            )
            return Decision(
                ALLOW, rec.reason, policy.component_id, capability_class, name, True, rec
            )
    return evaluate_request(
        policy, capability_class, name, log=log, evaluator_name="grant-beats-deny"
    )


def subprocess_bypass_evaluator(
    policy: Policy,
    capability_class: str,
    name: str,
    log: list[AuditRecord],
) -> Decision:
    """Mutant: subprocess skips the choke point."""
    if capability_class == "subprocess":
        return Decision(
            ALLOW,
            "subprocess-bypass",
            policy.component_id,
            capability_class,
            name,
            False,
            None,
        )
    return evaluate_request(
        policy, capability_class, name, log=log, evaluator_name="subprocess-bypass"
    )


class PermissionGate:
    """Runtime choke point: evaluate then act. Denied actions do not execute."""

    def __init__(
        self,
        policy: Policy,
        evaluator: Evaluator = reference_evaluator,
        *,
        execute_on_deny: bool = False,
        skip_validation: bool = False,
    ) -> None:
        if not skip_validation:
            validate_or_raise(policy)
        self.policy = policy
        self.evaluator = evaluator
        self.execute_on_deny = execute_on_deny
        self.audit_log: list[AuditRecord] = []
        self.trace = SideEffectTrace()

    def check(self, capability_class: str, name: str) -> Decision:
        return self.evaluator(self.policy, capability_class, name, self.audit_log)

    def _act(self, decision: Decision) -> bool:
        return decision.decision == ALLOW or self.execute_on_deny

    def attempt_tool(self, tool: str) -> Decision:
        return self.check("tool_call", tool)

    def attempt_write(self, path: Path, payload: bytes) -> Decision:
        decision = self.check("file_path", str(path))
        if self._act(decision):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            self.trace.writes.append(str(path))
        return decision

    def attempt_spawn(self, argv: list[str]) -> Decision:
        name = argv[0] if argv else ""
        decision = self.check("subprocess", name)
        if self._act(decision):
            subprocess.run(argv, check=False, capture_output=True, text=True)
            self.trace.spawns.append(list(argv))
        return decision

    def attempt_connect(self, host: str, port: int, timeout: float = 0.05) -> Decision:
        target = f"{host}:{port}"
        decision = self.check("network_egress", target)
        if self._act(decision):
            try:
                with socket.create_connection((host, port), timeout=timeout):
                    pass
            except OSError:
                pass
            self.trace.connects.append(target)
        return decision

    def attempt_credential_read(self, name: str) -> Decision:
        decision = self.check("credential_read", name)
        if self._act(decision):
            self.trace.credential_reads.append(name)
        return decision


def narrow_plugin_policy(component_id: str = "narrow-plugin") -> Policy:
    return Policy(
        component_id=component_id,
        evaluation_locus=EVALUATION_LOCUS,
        grants=[
            Rule("tool_call", "Read", "grant"),
            Rule("tool_call", "Grep", "grant"),
            Rule("file_path", "*/scratch/*", "grant"),
        ],
        denies=[
            Rule("file_path", "*/outside/*", "deny"),
            Rule("tool_call", "Bash", "deny"),
        ],
        wildcard_credential_read=WILDCARD_CREDENTIAL_READ,
        least_privilege_statement=(
            "Declared permissions must be a superset of observed use; "
            "undeclared capability requests are denied and logged."
        ),
    )


def overlapping_grant_deny_policy() -> Policy:
    """Read is both granted and denied: deny must win."""
    return Policy(
        component_id="overlap-plugin",
        evaluation_locus=EVALUATION_LOCUS,
        grants=[
            Rule("tool_call", "Read", "grant"),
            Rule("tool_call", "Grep", "grant"),
        ],
        denies=[Rule("tool_call", "Read", "deny")],
        wildcard_credential_read=WILDCARD_CREDENTIAL_READ,
        least_privilege_statement=(
            "Declared permissions must be a superset of observed use; "
            "undeclared capability requests are denied and logged."
        ),
    )


def observed_uses_ok() -> tuple[list[str], list[str]]:
    return ["Read", "Grep"], ["Read", "Grep"]


def observed_uses_undeclared() -> tuple[list[str], list[str]]:
    return ["Read", "Grep"], ["Read", "Bash"]


def least_privilege_holds(declared: Iterable[str], observed: Iterable[str]) -> bool:
    return set(observed).issubset(set(declared))


def census_path(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "size": path.stat().st_size if path.exists() and path.is_file() else 0,
        "pid": os.getpid(),
    }
