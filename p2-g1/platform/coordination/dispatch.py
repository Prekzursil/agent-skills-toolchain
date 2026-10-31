"""The cross-vendor dispatch contract: a completion AND-gate, and a mechanical plan audit.

THE THREE-WAY CONTRADICTION, AND WHY IT IS ONLY APPARENT
--------------------------------------------------------
Three estate documents give instructions that cannot all be obeyed as literally written:

  (a) ``rules/common/cross-vendor-dispatch.md:7-9`` - "A work-unit dispatch MUST block.
      Fire-and-forget is banned. NEVER ``--background``, ``&``, ``nohup``, ``spawn(detached)``, or
      ``run_in_background`` for a dispatch whose result a barrier is waiting on."
  (b) ``rules/common/cross-vendor-dispatch.md:64-66`` (the SAME document, section 7) - "Any agent
      that shells to another agent runtime must set an EXPLICIT Bash timeout (30 min) and run under
      ``longrun`` (AGENTS.md section 4a)."
  (c) ``C:/Users/Prekzursil/.claude/AGENTS.md:59-64`` section 4a - anything over 60s "MUST run via
      ``longrun`` with ``run_in_background``/``Monitor`` - never a blocking foreground call."
  (d) ``C:/Users/Prekzursil/.claude/agents/codex.md:52-55`` - "``longrun`` BACKGROUNDS ITS CHILD, so
      ``codex ... - < prompt.txt`` never receives stdin and dies with 'No prompt provided via
      stdin.' Put the redirect INSIDE a runner script that ``longrun`` calls."

Note first that the collision is INTERNAL to one document: (a) bans ``run_in_background`` and (b),
eleven paragraphs later in the same file, mandates the wrapper whose documented behaviour is to
background its child. A reader who follows (a) literally violates (b) and (c); a reader who follows
(c) literally violates (a).

THE RESOLUTION: TRANSPORT AND CONTRACT ARE DIFFERENT AXES
--------------------------------------------------------
Read (a) against its own evidence rather than its headline. Its bullets 2 and 3 say what it is
actually protecting against: *"NEVER return a job id, a 'started in the background as task-...'
string, or a 'Check /codex:status' receipt as a work-unit result"*, and *"a backgrounded job's
result is unreachable in practice: jobs written from a subagent carry ``sessionId: null``, and
``lib/job-control.mjs:19`` filters ``/codex:status`` by session id, so ``null === "<id>"`` hides
every one of them."*

Both are statements about the RESULT CHANNEL and the CALLER'S CONTRACT, not about OS process
topology. The banned thing is a dispatcher that RETURNS before the unit reaches a terminal state,
and a result channel the dispatcher cannot read. Neither is entailed by the child being detached.

So the contract this platform adopts, and enforces in :func:`audit_plan`:

  * **Logical contract: BLOCKING BARRIER.** The dispatch call does not return until the unit
    reaches a terminal state. Non-negotiable; this is what (a) is really asking for.
  * **Transport: detachment PERMITTED, but only WITH a barrier.** ``longrun`` +
    ``run_in_background`` satisfies (b) and (c). Detachment without a declared barrier is exactly
    the banned fire-and-forget and is a violation.
  * **Result channel: a FILE the dispatcher reads itself** (``-o last-message.json``). Never a job
    store keyed by a session id the subagent does not have; never the ``[codex] ...`` progress
    stream.
  * **Prompt delivery: a runner script owns the redirect.** Because the child is detached it does
    not inherit stdin, so ``- < prompt.txt`` AT THE longrun CALL SITE cannot work - (d). And never
    inline: Windows caps a command line at 32,767 chars and an inline prompt measured
    ``payload_len=34472`` -> ``os error 206``.
  * **The runner script must end with ``rc=$?; exit "$rc"``.** A trailing bare ``echo`` overwrites
    ``$?`` and once masked a codex exit 1 as SUCCESS in 7s with no output file.

That set is consistent, it satisfies every one of (a)-(d)'s actual protections, and it is the
ABSTRACTION LEAK the spec asks to be made explicit: the transport's process topology leaks into the
adapter's prompt-delivery contract. It is recorded as L-01/L-02 in ABSTRACTION-LEAKS.md and as data
in :data:`RESOLUTION` here, with ``test_dispatch.py`` asserting the prose and the audit agree.

THE COMPLETION AND-GATE
-----------------------
Exit code zero alone is never success (spec line 10646, and
``cross-vendor-dispatch.md:29-33``). :func:`verify_dispatch` requires ALL of: exit 0, AND an output
file that exists and is non-empty and parses, AND schema validity. A missing schema makes the third
limb ``NOT-CHECKED``, which BLOCKS - an unmeasured limb is never folded into a pass.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

__all__ = [
    "DEFAULT_SILENT_TIMEOUT_MS",
    "DispatchCheck",
    "DispatchPlan",
    "DispatchVerdict",
    "FORGED_RECEIPT_PATTERNS",
    "Limb",
    "LimbResult",
    "PlanAudit",
    "PlanViolation",
    "RESOLUTION",
    "REQUIRED_TIMEOUT_MS",
    "audit_plan",
    "forged_receipt_matches",
    "verify_dispatch",
]

#: The Bash-tool default that ``cross-vendor-dispatch.md:64-66`` forbids relying on.
DEFAULT_SILENT_TIMEOUT_MS = 600_000
#: The explicit 30-minute timeout the same section mandates.
REQUIRED_TIMEOUT_MS = 1_800_000

#: The resolution, as data, so a test can assert the prose and the enforcement agree.
RESOLUTION: Mapping[str, Any] = {
    "logical_contract": "BLOCKING-BARRIER",
    "transport": "DETACHED-CHILD-PERMITTED-WITH-BARRIER",
    "result_channel": "CALLER-READ-OUTPUT-FILE",
    "prompt_delivery": ("runner-script", "prompt-file"),
    "banned_prompt_delivery": ("inline", "stdin-redirect-under-detach"),
    "stdin_inherited_by_detached_child": False,
    "runner_must_end_with": 'rc=$?; exit "$rc"',
    "sources": {
        "a_ban": "rules/common/cross-vendor-dispatch.md:7-9",
        "b_longrun_mandate_same_doc": "rules/common/cross-vendor-dispatch.md:64-66",
        "c_agents_4a": "C:/Users/Prekzursil/.claude/AGENTS.md:59-64",
        "d_stdin_leak": "C:/Users/Prekzursil/.claude/agents/codex.md:52-55",
        "e_and_gate": "rules/common/cross-vendor-dispatch.md:29-33",
        "f_arg_limit": "rules/common/cross-vendor-dispatch.md:34-40",
        "g_trailing_echo": "C:/Users/Prekzursil/.claude/agents/codex.md:56-58",
        "h_inert_sandbox": "C:/Users/Prekzursil/.claude/agents/codex.md:44-50",
    },
    "why_not_a_contradiction": (
        "(a) bans a dispatcher that RETURNS before terminal state and a result channel the "
        "dispatcher cannot read - both properties of the CONTRACT. (c) constrains the TRANSPORT. A "
        "detached child with a blocking barrier and a caller-read output file satisfies both."
    ),
}


# ------------------------------------------------------------------ the completion AND-gate


class Limb(str, Enum):
    EXIT_ZERO = "exit-zero"
    ARTIFACT_PRESENT = "artifact-present"
    ARTIFACT_PARSES = "artifact-parses"
    SCHEMA_VALID = "schema-valid"
    NOT_A_JOB_RECEIPT = "not-a-job-receipt"


class DispatchVerdict(str, Enum):
    SUCCESS = "SUCCESS"
    #: exit 0 but the result channel produced nothing usable.
    SEVERED = "SEVERED"
    EXIT_NONZERO = "EXIT-NONZERO"
    SCHEMA_INVALID = "SCHEMA-INVALID"
    #: A limb could not be evaluated. Blocks; never folded into a pass.
    NOT_CHECKED = "NOT-CHECKED"
    #: The "result" is a job receipt / progress stream, not a work product.
    FORGED_RECEIPT = "FORGED-RECEIPT"


#: The cheap regex from the fan-out contract ("Reject any result containing 'started in the
#: background' or 'Check /codex:status'"). Implemented as specified.
#:
#: KNOWN AND MEASURED LIMITATION: this is a use-vs-mention detector and it cannot tell a job
#: receipt from a document that QUOTES one. ``test_dispatch.py`` carries the false positive
#: explicitly (a legitimate payload discussing the pattern is flagged), so the exposure is a
#: measured fact rather than a hypothetical. Mitigation available to callers: scan only the raw
#: stdout tail, and rely on the structural limbs for the payload.
FORGED_RECEIPT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("started in the background", r"started\s+in\s+the\s+background"),
    ("check-codex-status", r"Check\s+/codex:status"),
    ("job-id-receipt", r"\bas\s+task-[0-9a-f]{6,}\b"),
)


def forged_receipt_matches(text: str) -> tuple[str, ...]:
    """Names of the forged-receipt patterns present in ``text``."""
    return tuple(
        name
        for name, pattern in FORGED_RECEIPT_PATTERNS
        if re.search(pattern, text, re.I)
    )


@dataclass(frozen=True)
class LimbResult:
    limb: Limb
    passed: bool
    checked: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "limb": self.limb.value,
            "passed": self.passed,
            "checked": self.checked,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DispatchCheck:
    unit_id: str
    verdict: DispatchVerdict
    limbs: tuple[LimbResult, ...]
    payload: Any | None = None

    @property
    def ok(self) -> bool:
        """POSITIVE form: every limb was CHECKED and every checked limb PASSED."""
        return (
            self.verdict is DispatchVerdict.SUCCESS
            and len(self.limbs) == len(Limb)
            and all(limb.checked and limb.passed for limb in self.limbs)
        )

    def limb(self, which: Limb) -> LimbResult:
        for result in self.limbs:
            if result.limb is which:
                return result
        raise KeyError(which)

    @property
    def sentinel_line(self) -> str:
        if self.ok:
            return (
                f"SUCCESS:{self.unit_id} dispatch limbs={len(self.limbs)}/{len(Limb)}"
            )
        failed = [
            limb.limb.value for limb in self.limbs if not (limb.checked and limb.passed)
        ]
        return f"FAILED:{self.unit_id} {self.verdict.value} limbs_failed={failed}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "dispatch_check",
            "unit_id": self.unit_id,
            "verdict": self.verdict.value,
            "ok": self.ok,
            "limbs": [limb.to_dict() for limb in self.limbs],
            "sentinel_line": self.sentinel_line,
        }


def _validate_against_schema(payload: Any, schema_path: Path) -> tuple[bool, str]:
    try:
        import jsonschema
    except ImportError:  # pragma: no cover - jsonschema is a project dependency
        return False, "jsonschema is not importable; the third limb cannot be evaluated"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return False, f"schema unreadable: {exc}"
    except json.JSONDecodeError as exc:
        return False, f"schema is not valid JSON: {exc}"
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    errors = sorted(
        validator_cls(schema).iter_errors(payload), key=lambda e: list(e.path)
    )
    if errors:
        first = errors[0]
        location = "/".join(str(p) for p in first.path) or "<root>"
        return (
            False,
            f"{len(errors)} schema error(s); first at {location}: {first.message}",
        )
    return True, f"validates against {schema_path.name}"


def verify_dispatch(
    *,
    unit_id: str,
    exit_code: int | None,
    output_path: str | Path | None,
    schema_path: str | Path | None = None,
    stdout_text: str = "",
    min_bytes: int = 2,
    scan_payload_for_forgery: bool = False,
) -> DispatchCheck:
    """The AND-gate. Exit 0 is one limb of five, never the verdict.

    ``min_bytes`` defaults to 2 (the shortest legal JSON document) because this gate measures the
    TRANSPORT ENVELOPE, not the work artifact. The artifact's "meaningful minimum size" is
    condition 3 of the shared completion predicate and belongs there, with its own per-class floors.
    """
    limbs: list[LimbResult] = []

    if exit_code is None:
        limbs.append(
            LimbResult(Limb.EXIT_ZERO, False, False, "no exit code was captured")
        )
    else:
        limbs.append(
            LimbResult(
                Limb.EXIT_ZERO,
                exit_code == 0,
                True,
                f"exit_code={exit_code}",
            )
        )

    payload: Any | None = None
    text: str | None = None
    if output_path is None:
        limbs.append(
            LimbResult(
                Limb.ARTIFACT_PRESENT,
                False,
                True,
                "no output path was declared; there is no result channel to read",
            )
        )
        limbs.append(LimbResult(Limb.ARTIFACT_PARSES, False, False, "nothing to parse"))
    else:
        p = Path(output_path)
        try:
            raw = p.read_bytes()
        except OSError as exc:
            limbs.append(
                LimbResult(Limb.ARTIFACT_PRESENT, False, True, f"unreadable: {exc}")
            )
            limbs.append(
                LimbResult(Limb.ARTIFACT_PARSES, False, False, "nothing to parse")
            )
        else:
            big_enough = len(raw) >= min_bytes
            limbs.append(
                LimbResult(
                    Limb.ARTIFACT_PRESENT,
                    big_enough,
                    True,
                    f"{len(raw)} bytes (min {min_bytes})",
                )
            )
            try:
                text = raw.decode("utf-8")
                payload = json.loads(text)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                limbs.append(
                    LimbResult(
                        Limb.ARTIFACT_PARSES, False, True, f"does not parse: {exc}"
                    )
                )
            else:
                limbs.append(
                    LimbResult(
                        Limb.ARTIFACT_PARSES,
                        True,
                        True,
                        f"parsed as {type(payload).__name__}",
                    )
                )

    if schema_path is None:
        limbs.append(
            LimbResult(
                Limb.SCHEMA_VALID,
                False,
                False,
                "no schema supplied - the third limb is NOT-CHECKED and blocks SUCCESS",
            )
        )
    elif payload is None:
        limbs.append(
            LimbResult(Limb.SCHEMA_VALID, False, False, "no payload to validate")
        )
    else:
        passed, detail = _validate_against_schema(payload, Path(schema_path))
        limbs.append(LimbResult(Limb.SCHEMA_VALID, passed, True, detail))

    forgery_text = stdout_text + (text if (scan_payload_for_forgery and text) else "")
    matches = forged_receipt_matches(forgery_text)
    limbs.append(
        LimbResult(
            Limb.NOT_A_JOB_RECEIPT,
            not matches,
            True,
            (
                f"forged-receipt patterns present: {list(matches)}"
                if matches
                else "no fire-and-forget receipt signature"
            ),
        )
    )

    verdict = _verdict_for(limbs)
    return DispatchCheck(
        unit_id=unit_id, verdict=verdict, limbs=tuple(limbs), payload=payload
    )


def _verdict_for(limbs: Sequence[LimbResult]) -> DispatchVerdict:
    by_limb = {limb.limb: limb for limb in limbs}
    if not by_limb[Limb.NOT_A_JOB_RECEIPT].passed:
        return DispatchVerdict.FORGED_RECEIPT
    exit_limb = by_limb[Limb.EXIT_ZERO]
    if exit_limb.checked and not exit_limb.passed:
        return DispatchVerdict.EXIT_NONZERO
    present = by_limb[Limb.ARTIFACT_PRESENT]
    parses = by_limb[Limb.ARTIFACT_PARSES]
    if not (present.checked and present.passed) or not (
        parses.checked and parses.passed
    ):
        # Exit 0 with no usable artifact is the SEVERED signature, not a failure of the work.
        return DispatchVerdict.SEVERED
    schema = by_limb[Limb.SCHEMA_VALID]
    if not schema.checked:
        return DispatchVerdict.NOT_CHECKED
    if not schema.passed:
        return DispatchVerdict.SCHEMA_INVALID
    if not exit_limb.checked:
        return DispatchVerdict.NOT_CHECKED
    return DispatchVerdict.SUCCESS


# ------------------------------------------------------------------------ the plan audit


@dataclass(frozen=True)
class DispatchPlan:
    """A proposed dispatch, in the terms the estate's rules are written in."""

    unit_id: str
    adapter_id: str
    argv: tuple[str, ...] = ()
    timeout_ms: int | None = None
    #: True when the transport detaches the child (longrun / run_in_background / nohup / &).
    background: bool = False
    #: How the caller blocks until terminal state. None = fire-and-forget.
    barrier: str | None = None
    #: "output-file" | "job-store" | "stdout"
    result_channel: str = "output-file"
    output_path: str | None = None
    #: "runner-script" | "prompt-file" | "stdin-redirect" | "inline"
    prompt_delivery: str = "runner-script"
    runner_script_text: str | None = None
    schema_path: str | None = None
    expected_duration_s: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "adapter_id": self.adapter_id,
            "argv": list(self.argv),
            "timeout_ms": self.timeout_ms,
            "background": self.background,
            "barrier": self.barrier,
            "result_channel": self.result_channel,
            "output_path": self.output_path,
            "prompt_delivery": self.prompt_delivery,
            "schema_path": self.schema_path,
            "expected_duration_s": self.expected_duration_s,
        }


@dataclass(frozen=True)
class PlanViolation:
    code: str
    message: str
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "source": self.source}


#: Every check the audit runs, in a fixed order. Used for the POSITIVE assertion: the audit is
#: clean only when all N ran, not merely when nothing complained.
AUDIT_CHECKS: tuple[str, ...] = (
    "V-01-unbarriered-detach",
    "V-02-job-store-result",
    "V-03-stdout-result",
    "V-04-stdin-under-detach",
    "V-05-inline-prompt",
    "V-06-missing-timeout",
    "V-07-silent-default-timeout",
    "V-08-missing-ignore-user-config",
    "V-09-long-run-in-foreground",
    "V-10-runner-trailing-echo",
    "V-11-backgrounding-token-in-argv",
    "V-12-inert-sandbox-flag",
    "V-13-no-output-path",
)


@dataclass(frozen=True)
class PlanAudit:
    plan: DispatchPlan
    checks_run: tuple[str, ...]
    violations: tuple[PlanViolation, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """N of N checks ran AND none fired. Never merely 'nothing blocking'."""
        return len(self.checks_run) == len(AUDIT_CHECKS) and not self.violations

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(v.code for v in self.violations)

    @property
    def sentinel_line(self) -> str:
        if self.ok:
            return (
                f"SUCCESS:plan/{self.plan.unit_id} checks={len(self.checks_run)}/"
                f"{len(AUDIT_CHECKS)} violations=0"
            )
        return (
            f"FAILED:plan/{self.plan.unit_id} checks={len(self.checks_run)}/{len(AUDIT_CHECKS)} "
            f"violations={list(self.codes)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "dispatch_plan_audit",
            "plan": self.plan.to_dict(),
            "checks_run": list(self.checks_run),
            "violations": [v.to_dict() for v in self.violations],
            "ok": self.ok,
            "sentinel_line": self.sentinel_line,
        }


_SRC = RESOLUTION["sources"]

#: Tokens that background a command line. Deliberately NARROW.
#:
#: DECLARED DETECTOR GAP: ``start`` (cmd.exe) and ``Start-Process`` also detach, and are NOT
#: matched here, because as bare argv tokens they collide with legitimate subcommands (``svc
#: start``) and the estate's measured lesson is that a matcher which fires on a mention rather
#: than a use is worse than one with a known hole. The hole is closed by ``plan.background``,
#: which the caller declares explicitly and which V-01 checks; this token scan is a second,
#: independent signal for the case where the caller declares foreground but the argv detaches
#: anyway. The experiment that would settle whether the gap matters: sweep real dispatch argvs
#: for ``start``/``Start-Process`` and count how many declare ``background=False``.
_BACKGROUNDING_TOKENS = ("--background", "nohup", "&")


def audit_plan(plan: DispatchPlan) -> PlanAudit:
    """Audit a proposed dispatch against the resolved contract.

    Every violation cites the document that establishes it, so a disagreement is arguable against
    a source rather than against this function's opinion.
    """
    v: list[PlanViolation] = []
    argv_lower = tuple(a.lower() for a in plan.argv)
    joined = " ".join(argv_lower)

    if plan.background and not plan.barrier:
        v.append(
            PlanViolation(
                "V-01-unbarriered-detach",
                "the transport detaches the child but no completion barrier is declared: this is "
                "fire-and-forget, and the dispatcher would return before terminal state",
                _SRC["a_ban"],
            )
        )
    if plan.result_channel == "job-store":
        v.append(
            PlanViolation(
                "V-02-job-store-result",
                "a job store is not a readable result channel from a subagent: jobs written from "
                "a subagent carry sessionId=null and the status filter compares it to the session "
                "id, hiding every one of them",
                _SRC["a_ban"],
            )
        )
    if plan.result_channel == "stdout":
        v.append(
            PlanViolation(
                "V-03-stdout-result",
                "the progress stream is not a result: a foreground call once returned after 6m59s "
                "carrying only a progress prefix which was forwarded as the answer",
                _SRC["e_and_gate"],
            )
        )
    if plan.background and plan.prompt_delivery == "stdin-redirect":
        v.append(
            PlanViolation(
                "V-04-stdin-under-detach",
                "a detached child does not inherit stdin, so '- < prompt.txt' at the wrapper call "
                "site dies with 'No prompt provided via stdin.' Move the redirect inside a runner "
                "script the wrapper calls",
                _SRC["d_stdin_leak"],
            )
        )
    if plan.prompt_delivery == "inline":
        v.append(
            PlanViolation(
                "V-05-inline-prompt",
                "Windows caps a command line at 32,767 chars; an inline prompt measured "
                "payload_len=34472 -> os error 206 and killed both runs that attempted real work",
                _SRC["f_arg_limit"],
            )
        )
    if plan.timeout_ms is None:
        v.append(
            PlanViolation(
                "V-06-missing-timeout",
                "no explicit timeout: the silent 10-minute default is what one agent rationalised "
                "--background to escape",
                _SRC["b_longrun_mandate_same_doc"],
            )
        )
    elif plan.timeout_ms == DEFAULT_SILENT_TIMEOUT_MS:
        v.append(
            PlanViolation(
                "V-07-silent-default-timeout",
                f"timeout_ms={plan.timeout_ms} is the silent default, not an explicit decision; "
                f"the rule requires an explicit {REQUIRED_TIMEOUT_MS} ms (30 min)",
                _SRC["b_longrun_mandate_same_doc"],
            )
        )
    if plan.adapter_id == "codex-cli" and "--ignore-user-config" not in argv_lower:
        v.append(
            PlanViolation(
                "V-08-missing-ignore-user-config",
                "--ignore-user-config is mandatory on a non-interactive codex invocation: the "
                "active MCP inventory blows the arg limit and voids --output-schema (issue #15451)",
                "rules/common/cross-vendor-dispatch.md:42-47",
            )
        )
    if (
        plan.expected_duration_s is not None
        and plan.expected_duration_s > 60
        and not plan.background
    ):
        v.append(
            PlanViolation(
                "V-09-long-run-in-foreground",
                f"expected_duration_s={plan.expected_duration_s} exceeds 60s but the transport is "
                "foreground; section 4a requires longrun with run_in_background above 60s",
                _SRC["c_agents_4a"],
            )
        )
    if plan.runner_script_text is not None:
        tail = [
            line.strip()
            for line in plan.runner_script_text.strip().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        last = tail[-1] if tail else ""
        if last.startswith("echo") or not re.search(
            r"exit\s+\"?\$\{?rc\}?\"?|exit\s+\$\?", last
        ):
            v.append(
                PlanViolation(
                    "V-10-runner-trailing-echo",
                    "the runner script must end with 'rc=$?; ...; exit \"$rc\"': a trailing bare "
                    "echo overwrites $? and once masked a codex exit 1 as SUCCESS in 7s with no "
                    f"output file (last non-comment line: {last!r})",
                    _SRC["g_trailing_echo"],
                )
            )
    bad_tokens = [t for t in _BACKGROUNDING_TOKENS if t in argv_lower]
    if bad_tokens:
        v.append(
            PlanViolation(
                "V-11-backgrounding-token-in-argv",
                f"argv carries backgrounding token(s) {bad_tokens}: detachment belongs to the "
                "wrapper under a declared barrier, never to the dispatched command line",
                _SRC["a_ban"],
            )
        )
    if (
        "--sandbox" in argv_lower
        and "workspace-write" in joined
        and plan.adapter_id == "codex-cli"
    ):
        v.append(
            PlanViolation(
                "V-12-inert-sandbox-flag",
                "--sandbox workspace-write is INERT on codex-cli 0.144.5 / Windows (-s, "
                "-c sandbox_mode and --full-auto all still print 'sandbox: read-only'); relying on "
                "it means believing in confinement that is not there",
                _SRC["h_inert_sandbox"],
            )
        )
    if not plan.output_path:
        v.append(
            PlanViolation(
                "V-13-no-output-path",
                "no output file is declared, so the AND-gate's second limb cannot be evaluated and "
                "the only remaining channel would be the progress stream",
                _SRC["e_and_gate"],
            )
        )

    return PlanAudit(plan=plan, checks_run=AUDIT_CHECKS, violations=tuple(v))


def audit_many(plans: Iterable[DispatchPlan]) -> tuple[PlanAudit, ...]:
    return tuple(audit_plan(p) for p in plans)
