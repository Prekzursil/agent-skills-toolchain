"""Conformance suite for the permission-model contract (TST-0036).

Each contract rule has a positive case (reference gate) and a negative
case (a mutant the suite must classify as non-conforming). Both-states:
the reference gate is conforming; a silent-grant mutant is not, and that
mutant is a P0.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from permission_model import (
    ALLOW,
    DENY,
    PermissionGate,
    Rule,
    deny_all_evaluator,
    grant_beats_deny_evaluator,
    least_privilege_holds,
    narrow_plugin_policy,
    observed_uses_ok,
    observed_uses_undeclared,
    overlapping_grant_deny_policy,
    silent_grant_evaluator,
    subprocess_bypass_evaluator,
    validate_policy,
)


@dataclass
class CaseResult:
    id: str
    rule: str
    kind: str
    pass_: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "rule": self.rule,
            "kind": self.kind,
            "pass": self.pass_,
            "detail": self.detail,
        }


def _case(cid: str, rule: str, kind: str, ok: bool, detail: str) -> CaseResult:
    return CaseResult(cid, rule, kind, bool(ok), detail)


def _positive_cases() -> list[CaseResult]:
    out: list[CaseResult] = []
    policy = narrow_plugin_policy()
    gate = PermissionGate(policy)

    undeclared = gate.attempt_tool("Write")
    undeclared_logged = any(
        r.name == "Write"
        and r.decision == DENY
        and r.reason == "undeclared-permission"
        for r in gate.audit_log
    )
    out.append(
        _case(
            "R1-P",
            "undeclared-permission-denied-and-logged",
            "positive",
            undeclared.decision == DENY
            and undeclared.reason == "undeclared-permission"
            and undeclared.logged
            and undeclared_logged,
            f"decision={undeclared.decision} reason={undeclared.reason} "
            f"logged={undeclared.logged}",
        )
    )

    allowed = gate.attempt_tool("Read")
    out.append(
        _case(
            "R2-P",
            "declared-request-granted",
            "positive",
            allowed.decision == ALLOW and allowed.logged,
            f"decision={allowed.decision} reason={allowed.reason}",
        )
    )

    overlap = PermissionGate(overlapping_grant_deny_policy())
    od = overlap.attempt_tool("Read")
    out.append(
        _case(
            "R3-P",
            "deny-precedes-grant",
            "positive",
            od.decision == DENY and od.reason.startswith("deny-rule:"),
            f"decision={od.decision} reason={od.reason}",
        )
    )

    wild = narrow_plugin_policy("wild")
    wild.grants.append(Rule("credential_read", "*", "grant"))
    wild_errors = validate_policy(wild)
    out.append(
        _case(
            "R4-P",
            "wildcard-credential-read-rejected-at-validation",
            "positive",
            any("wildcard credential_read" in e for e in wild_errors),
            f"errors={wild_errors}",
        )
    )

    hits = []
    for cls, name in (
        ("tool_call", "Read"),
        ("file_path", "/tmp/scratch/a.txt"),
        ("network_egress", "example.invalid:443"),
        ("subprocess", "/bin/true"),
        ("credential_read", "OPENAI_API_KEY"),
    ):
        dec = gate.check(cls, name)
        hits.append((cls, dec.decision, dec.logged))
    out.append(
        _case(
            "R5-P",
            "single-evaluation-locus-all-capability-classes",
            "positive",
            len(hits) == 5
            and all(logged for _, _, logged in hits)
            and any(cls == "credential_read" and decision == DENY for cls, decision, _ in hits),
            f"hits={hits}",
        )
    )

    with tempfile.TemporaryDirectory(prefix="tst0036-suite-") as tmp:
        root = Path(tmp)
        outside = root / "outside" / "secret.txt"
        marker = root / "spawned.txt"
        write_dec = gate.attempt_write(outside, b"should-not-land")
        spawn_dec = gate.attempt_spawn(
            ["python3", "-c", f"open({str(marker)!r}, 'w').write('spawned')"]
        )
        connect_dec = gate.attempt_connect("203.0.113.1", 1)
        cred_dec = gate.attempt_credential_read("OPENAI_API_KEY")
        scratch = root / "scratch" / "ok.txt"
        ok_write = gate.attempt_write(scratch, b"ok")
        out.append(
            _case(
                "R6-P",
                "denied-action-has-no-side-effect",
                "positive",
                write_dec.decision == DENY
                and spawn_dec.decision == DENY
                and connect_dec.decision == DENY
                and cred_dec.decision == DENY
                and not outside.exists()
                and not marker.exists()
                and "203.0.113.1:1" not in gate.trace.connects
                and "OPENAI_API_KEY" not in gate.trace.credential_reads
                and ok_write.decision == ALLOW
                and scratch.exists(),
                (
                    f"write={write_dec.decision} exists={outside.exists()} "
                    f"spawn={spawn_dec.decision} marker={marker.exists()} "
                    f"connect={connect_dec.decision} cred={cred_dec.decision} "
                    f"ok_write={ok_write.decision} scratch={scratch.exists()}"
                ),
            )
        )

    declared, observed = observed_uses_ok()
    out.append(
        _case(
            "R7-P",
            "least-privilege-observed-subset-declared",
            "positive",
            least_privilege_holds(declared, observed),
            f"declared={declared} observed={observed}",
        )
    )
    return out


def _negative_cases() -> list[CaseResult]:
    """Mutants: the case PASSES when the mutant is observably non-conforming."""
    out: list[CaseResult] = []
    policy = narrow_plugin_policy()

    silent = PermissionGate(policy, silent_grant_evaluator)
    sd = silent.attempt_tool("Write")
    out.append(
        _case(
            "R1-N",
            "undeclared-permission-denied-and-logged",
            "negative",
            sd.decision == ALLOW and not sd.logged and len(silent.audit_log) == 0,
            "silent-grant mutant granted Write with empty audit log",
        )
    )

    deny_all = PermissionGate(policy, deny_all_evaluator)
    dd = deny_all.attempt_tool("Read")
    out.append(
        _case(
            "R2-N",
            "declared-request-granted",
            "negative",
            dd.decision == DENY,
            "deny-all mutant refused a declared Read",
        )
    )

    gbd = PermissionGate(overlapping_grant_deny_policy(), grant_beats_deny_evaluator)
    gd = gbd.attempt_tool("Read")
    out.append(
        _case(
            "R3-N",
            "deny-precedes-grant",
            "negative",
            gd.decision == ALLOW,
            "grant-beats-deny mutant allowed overlapping Read",
        )
    )

    wild = narrow_plugin_policy("wild-n")
    wild.grants.append(Rule("credential_read", "API_*", "grant"))
    skipped = PermissionGate(wild, skip_validation=True)
    cd = skipped.attempt_credential_read("API_TOKEN")
    out.append(
        _case(
            "R4-N",
            "wildcard-credential-read-rejected-at-validation",
            "negative",
            any("wildcard credential_read" in e for e in validate_policy(wild))
            and cd.decision == ALLOW,
            f"skip-validation mutant granted API_TOKEN decision={cd.decision}",
        )
    )

    bypass = PermissionGate(policy, subprocess_bypass_evaluator)
    bd = bypass.check("subprocess", "/bin/true")
    out.append(
        _case(
            "R5-N",
            "single-evaluation-locus-all-capability-classes",
            "negative",
            bd.decision == ALLOW and not bd.logged,
            "subprocess-bypass mutant skipped the choke point",
        )
    )

    with tempfile.TemporaryDirectory(prefix="tst0036-neg-") as tmp:
        outside = Path(tmp) / "outside" / "leaked.txt"
        theater = PermissionGate(policy, execute_on_deny=True)
        td = theater.attempt_write(outside, b"leaked")
        out.append(
            _case(
                "R6-N",
                "denied-action-has-no-side-effect",
                "negative",
                td.decision == DENY and outside.exists(),
                "log-but-execute mutant denied the write but still wrote the file",
            )
        )

    declared, observed = observed_uses_undeclared()
    out.append(
        _case(
            "R7-N",
            "least-privilege-observed-subset-declared",
            "negative",
            not least_privilege_holds(declared, observed),
            f"undeclared observed use Bash not in {declared}",
        )
    )
    return out


def gate_is_conforming(gate: PermissionGate) -> dict[str, Any]:
    undeclared = gate.attempt_tool("Write")
    declared = gate.attempt_tool("Read")
    with tempfile.TemporaryDirectory(prefix="tst0036-accept-") as tmp:
        outside = Path(tmp) / "outside" / "x.txt"
        write_dec = gate.attempt_write(outside, b"x")
        leaked = outside.exists()
    conforming = (
        undeclared.decision == DENY
        and undeclared.logged
        and any(r.name == "Write" and r.decision == DENY for r in gate.audit_log)
        and declared.decision == ALLOW
        and write_dec.decision == DENY
        and not leaked
    )
    return {
        "conforming": conforming,
        "undeclared": undeclared.decision,
        "undeclared_logged": undeclared.logged,
        "declared": declared.decision,
        "write": write_dec.decision,
        "leaked": leaked,
        "audit_len": len(gate.audit_log),
    }


def both_states() -> dict[str, Any]:
    good = gate_is_conforming(PermissionGate(narrow_plugin_policy()))
    bad = gate_is_conforming(
        PermissionGate(narrow_plugin_policy(), silent_grant_evaluator)
    )
    return {
        "reference_conforming": good["conforming"],
        "silent_grant_conforming": bad["conforming"],
        "discriminates": good["conforming"] is True and bad["conforming"] is False,
        "reference": good,
        "silent_grant": bad,
    }


def run_suite() -> dict[str, Any]:
    cases = _positive_cases() + _negative_cases()
    both = both_states()
    positives = [c for c in cases if c.kind == "positive"]
    negatives = [c for c in cases if c.kind == "negative"]
    failed = [c.as_dict() for c in cases if not c.pass_]
    ok = (
        not failed
        and both["discriminates"]
        and len(positives) >= 7
        and len(negatives) >= 7
    )
    return {
        "pass": ok,
        "n_cases": len(cases),
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "failed": failed,
        "cases": [c.as_dict() for c in cases],
        "both_states": both,
        "rules": sorted({c.rule for c in cases}),
    }
