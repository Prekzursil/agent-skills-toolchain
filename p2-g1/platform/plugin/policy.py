"""Two declared policies: how plugin-shipped scripts may execute, and what fails open vs closed.

**Execution policy (IMP-0064).** A plugin ships code. The policy says, per entrypoint kind, what
it is allowed to do: which interpreter, whether it may be run automatically or only on explicit
invocation, whether network egress is permitted, and whether it may read the environment for
credentials (never — the credential boundary is injection-only, IMP-0061).

**Failure policy (IMP-0053).** Each component declares fail-open or fail-closed *and the reason*.
The default is fail-closed; fail-open is allowed only where the component is a pure accelerator
whose absence degrades speed, not correctness. Exactly one row is fail-open today (the cache) and
the table is asserted against the error taxonomy so the two cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import BY_CODE, TAXONOMY

EXEC_ON_EXPLICIT = "explicit-invocation-only"
EXEC_ON_INSTALL = "on-install"
EXEC_AUTOMATIC = "automatic"


@dataclass(frozen=True)
class ExecRule:
    kind: str
    trigger: str
    interpreter_required: bool
    network_allowed: bool
    credential_read_allowed: bool
    rationale: str

    def as_dict(self) -> dict[str, object]:
        return {
            "entrypoint_kind": self.kind,
            "trigger": self.trigger,
            "interpreter_required": self.interpreter_required,
            "network_allowed": self.network_allowed,
            "credential_read_allowed": self.credential_read_allowed,
            "rationale": self.rationale,
        }


EXEC_RULES: tuple[ExecRule, ...] = (
    ExecRule(
        "command",
        EXEC_ON_EXPLICIT,
        True,
        False,
        False,
        "a command runs only when the user types it; no ambient network, no credential store read",
    ),
    ExecRule(
        "hook",
        EXEC_AUTOMATIC,
        True,
        False,
        False,
        "hooks fire on every matching event, so they must be cheap, offline, and fail-open in "
        "their own body (a raising hook must not break the session)",
    ),
    ExecRule(
        "script",
        EXEC_ON_EXPLICIT,
        True,
        False,
        False,
        "shipped scripts are never auto-run by install; the installer only places them",
    ),
    ExecRule(
        "skill",
        EXEC_ON_EXPLICIT,
        False,
        False,
        False,
        "a skill is instructions, not an executable; it declares no interpreter",
    ),
)


def exec_policy_document() -> dict[str, object]:
    """The exec-policy artifact (tools/plugin/schema/exec-policy.schema.json)."""
    return {
        "artifact": "exec-policy",
        "default_trigger": EXEC_ON_EXPLICIT,
        "install_runs_shipped_code": False,
        "credential_boundary": "injected-environment-only; the plugin never reads a credential store",
        "rules": [r.as_dict() for r in EXEC_RULES],
    }


@dataclass(frozen=True)
class FailureRule:
    component: str
    mode: str  # fail-open | fail-closed
    error_code: str
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "component": self.component,
            "mode": self.mode,
            "error_code": self.error_code,
            "reason": self.reason,
        }


FAILURE_RULES: tuple[FailureRule, ...] = (
    FailureRule(
        "manifest-parser",
        "fail-closed",
        "E_MANIFEST",
        "an unparseable manifest cannot be installed safely at any severity",
    ),
    FailureRule(
        "payload-allowlist",
        "fail-closed",
        "E_PAYLOAD",
        "shipping unintended content is the spec's one explicit prohibition",
    ),
    FailureRule(
        "secret-gate",
        "fail-closed",
        "E_SECRET",
        "a leaked credential is unrecoverable once published",
    ),
    FailureRule(
        "size-budget",
        "fail-closed",
        "E_BUDGET",
        "an accidental multi-gigabyte artifact is a failure even if every command works",
    ),
    FailureRule(
        "preflight",
        "fail-closed",
        "E_PREFLIGHT",
        "a mutation with no space to complete corrupts state",
    ),
    FailureRule(
        "prefix-lock",
        "fail-closed",
        "E_LOCK",
        "two concurrent mutations interleave unrecoverably",
    ),
    FailureRule(
        "transaction",
        "fail-closed",
        "E_TXN",
        "a partially applied lifecycle op is the worst state",
    ),
    FailureRule(
        "drift-classifier",
        "fail-closed",
        "E_DRIFT",
        "auto-resolving a diverged file destroys content; the classifier refuses",
    ),
    FailureRule(
        "cache",
        "fail-open",
        "E_CACHE",
        "the cache is a pure accelerator: a corrupt entry is quarantined and the operation "
        "continues from source, so a broken accelerator is not an outage",
    ),
    FailureRule(
        "health-probe",
        "fail-closed",
        "E_HEALTH",
        "a probe that raises is a FAIL, never a silent pass",
    ),
    FailureRule(
        "conformance",
        "fail-closed",
        "E_CONFORM",
        "an unverifiable package must not publish",
    ),
    FailureRule(
        "migration",
        "fail-closed",
        "E_MIGRATE",
        "a half-migrated layout is unrecoverable without the ledger",
    ),
    FailureRule(
        "compatibility",
        "fail-closed",
        "E_COMPAT",
        "running on an unsupported client produces silent misbehaviour",
    ),
    FailureRule(
        "interpreter-probe",
        "fail-closed",
        "E_INTERP",
        "an inferred interpreter is how CRLF/WSL breakage ships",
    ),
    FailureRule(
        "filesystem",
        "fail-closed",
        "E_IO",
        "a path escape or reserved device name writes outside the prefix",
    ),
)


def failure_policy_document() -> dict[str, object]:
    """The failure-policy artifact (tools/plugin/schema/failure-policy.schema.json)."""
    return {
        "artifact": "failure-policy",
        "default_mode": "fail-closed",
        "fail_open_count": sum(1 for r in FAILURE_RULES if r.mode == "fail-open"),
        "rules": [r.as_dict() for r in FAILURE_RULES],
    }


def policy_taxonomy_agreement() -> list[str]:
    """Every disagreement between this table and the error taxonomy's own ``fail_mode`` column."""
    problems: list[str] = []
    for rule in FAILURE_RULES:
        klass = BY_CODE.get(rule.error_code)
        if klass is None:
            problems.append(
                f"{rule.component}: error code {rule.error_code} is not in the taxonomy"
            )
        elif klass.fail_mode != rule.mode:
            problems.append(
                f"{rule.component}: policy says {rule.mode} but taxonomy {rule.error_code} says {klass.fail_mode}"
            )
    covered = {r.error_code for r in FAILURE_RULES}
    for klass in TAXONOMY:
        if klass.code == "E_USAGE":
            continue  # usage is not a component
        if klass.code not in covered:
            problems.append(
                f"taxonomy code {klass.code} has no component in the failure policy"
            )
    return problems
