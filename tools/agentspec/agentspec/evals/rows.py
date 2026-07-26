"""The regression-eval ROW BODIES: R1-R6 and R8.

Each row is a MEASURED past failure. Each returns ``(passed, detail)`` and reaches the production
code ONLY through the injected :class:`~agentspec.evals.impl.Impl`, so
``tests/test_mutations.py`` can neuter one seam and require that row to go RED. A row that stays
green under its own mutant protects nothing — the failure mode 100% coverage cannot see.

Every row also carries a CONTROL in the good direction (the guard must not over-reach), because
a check that refuses valid work is as broken as one that permits invalid work.

Fully hermetic: the only rail is :class:`~agentspec.evals.fake_rail.FakeRail` and the only clock
is :class:`~agentspec.clock.FixedClock`. Zero network, zero vendor calls, zero real time.
"""

from __future__ import annotations

from pathlib import Path

import agentspec
from agentspec.argv import (
    WINDOWS_CMDLINE_CAP,
    ArgvPlan,
    PolicyViolation,
    PromptOnArgv,
    RailSpec,
    build_argv,
)
from agentspec.clock import FixedClock
from agentspec.evals.fake_rail import DispatchRefused, FakeRail, ScriptedResponse
from agentspec.evals.impl import Impl
from agentspec.oracle import RailResult, observe
from agentspec.progress import BACKGROUND_PHRASES, ProgressLog
from agentspec.spec import ReceiptSpec

JSON_SPEC = ReceiptSpec(fmt="json", required_fields=("status", "summary"))
TEXT_SPEC = ReceiptSpec(fmt="text", forbidden_markers=("in progress", "unable to"))
GOOD_JSON = b'{"status":"ok","summary":"3 files changed"}'

CODEX_RAIL = RailSpec(
    name="codex",
    exe="codex.exe",
    hardening=("--ignore-user-config",),
    prompt_transport="file",
    prompt_flag="--output-last-message",
)


def r1_no_background_on_an_awaited_dispatch(impl: Impl) -> tuple[bool, str]:
    """R1 — fire-and-forget on a barrier-awaited dispatch must be refused.

    MEASURED: three Codex-backed subagents produced zero artifacts because each returned a
    "started in the background as task-…" receipt; the real work then completed on disk and was
    discarded unread, since a backgrounded job's result is unreachable to its barrier.
    """
    rail, plan = _rail(impl, ScriptedResponse(exit_code=0, receipt=GOOD_JSON))
    try:
        rail.dispatch(
            unit_id="u1", plan=plan, timeout_s=1800, awaited=True, background=True
        )
    except DispatchRefused:
        pass
    else:
        return False, "the rail LAUNCHED a backgrounded awaited dispatch"

    # The rail exercise above already proves the predicate refuses this exact shape (the rail
    # calls the SAME injected policy with the SAME arguments), so re-asserting it here would be
    # an arm no mutant can reach. What still needs its own assertion is the CONTROL: the guard
    # must not over-reach onto a dispatch nothing is awaiting.
    if impl.check_dispatch(background=True, timeout_s=1800, awaited=False) != ():
        return (
            False,
            "control failed: a backgrounded UNAWAITED dispatch was refused too",
        )
    return (
        True,
        "backgrounding an awaited dispatch is refused; unawaited is still allowed",
    )


def r2_exit_zero_without_a_usable_receipt_is_severed(impl: Impl) -> tuple[bool, str]:
    """R2 — exit 0 plus a missing/empty/unparseable/invalid receipt is SEVERED, never SUCCESS.

    MEASURED: a foreground dispatch returned after 6m59s carrying only a progress prefix and the
    caller forwarded that as its terminal result while the job still read ``running``.
    """
    cases: tuple[tuple[str, bytes | None], ...] = (
        ("missing", None),
        ("empty", b""),
        ("whitespace", b"   \r\n"),
        ("unparseable", b"{not json"),
        ("schema-invalid", b'{"status":"ok"}'),
    )
    for label, body in cases:
        verdict = impl.judge(
            "u1", RailResult(exit_code=0, receipt_bytes=body), JSON_SPEC
        )
        if verdict.ok:
            return False, f"{label}: exit 0 with an unusable receipt reported SUCCESS"
        if not verdict.severed:
            return False, f"{label}: the verdict was not flagged severed"
        line = impl.terminal_line(verdict)
        if "severed-stream" not in line:
            return False, f"{label}: the terminal line {line!r} omits severed-stream"

    good = impl.judge("u1", RailResult(exit_code=0, receipt_bytes=GOOD_JSON), JSON_SPEC)
    if not good.ok:
        return False, "control failed: a fully good run did not report SUCCESS"
    return (
        True,
        f"{len(cases)} unusable-receipt shapes are severed; a good run still passes",
    )


def r3_a_progress_payload_is_never_a_result(impl: Impl) -> tuple[bool, str]:
    """R3 — a background-job receipt phrase or a bare progress stream is rejected as a result."""
    for phrase in BACKGROUND_PHRASES:
        if not isinstance(
            impl.classify(f"Job accepted. {phrase} as task-91af."), ProgressLog
        ):
            return False, f"the phrase {phrase!r} was accepted as a result"
    if not isinstance(impl.classify("[codex] thinking\n[codex] done\n"), ProgressLog):
        return False, "a bare bracketed progress stream was accepted as a result"
    if isinstance(impl.classify("The answer is 42."), ProgressLog):
        return False, "control failed: a real answer was rejected as progress"

    body = b"started in the background as task-1"
    if impl.judge("u1", RailResult(exit_code=0, receipt_bytes=body), TEXT_SPEC).ok:
        return False, "a progress payload written as the receipt reported SUCCESS"
    return (
        True,
        f"{len(BACKGROUND_PHRASES)} phrases plus a progress stream are all rejected",
    )


def r4_a_large_prompt_is_routed_off_argv(impl: Impl) -> tuple[bool, str]:
    """R4 — a 40 KB prompt travels by file/stdin and argv stays under the Windows cap.

    MEASURED: an inline prompt produced ``payload_len=34472`` and killed the run with
    ``os error 206``. Cap 32,767, measured via libuv at 32,745 OK / 32,774 ENAMETOOLONG.

    All THREE prompt-on-argv rules are exercised here: the bare-argument and
    ``--flag=<body>`` shapes via the transports above, and bare CONTAINMENT via the
    ``embedded`` case — the rule whose threshold constant was measurably unprotected.
    """
    prompt = "x" * 40_960
    plan = impl.build_argv(
        exe="codex.exe",
        prompt=prompt,
        transport="file",
        flags=("exec", "--ignore-user-config"),
        prompt_flag="--output-last-message",
        prompt_path="C:/tmp/p.txt",
    )
    if plan.cmdline_len >= WINDOWS_CMDLINE_CAP:
        return (
            False,
            f"a routed 40 KB prompt still produced {plan.cmdline_len} argv chars",
        )
    if any(prompt in element for element in plan.argv):
        return False, "the prompt reached argv despite the file transport"
    if (
        impl.build_argv(exe="grok.exe", prompt=prompt, transport="stdin").stdin_payload
        != prompt
    ):
        return False, "the stdin transport did not carry the prompt"

    # The prompt EMBEDDED in a larger argv element, with the whole command line far UNDER the
    # cap. Neither the cap check nor the equality / `--flag=<body>` rules can see this shape,
    # so it is the only assertion that exercises bare containment. It exists because the
    # adversarial critic MEASURED (2026-07-26) that raising MIN_SUBSTRING_SCAN_LEN disabled
    # that rule while the suite stayed at 366 passed and coverage stayed at 100.00%.
    embedded = "x" * 3_000
    try:
        impl.build_argv(
            exe="codex.exe",
            prompt=embedded,
            transport="stdin",
            flags=("exec", "the task is: " + embedded),
        )
    except PromptOnArgv:
        pass
    else:
        return (
            False,
            "a 3,000-char prompt embedded in a larger argv element was accepted",
        )

    over = "b" * (WINDOWS_CMDLINE_CAP + 1 - len("c.exe") - 1)
    try:
        impl.build_argv(exe="c.exe", prompt="p", transport="stdin", flags=(over,))
    except ValueError as exc:
        if getattr(exc, "reason", "") != "win-arg-limit":
            return False, f"over-cap argv raised {exc!r} instead of win-arg-limit"
    else:
        return False, f"argv of {WINDOWS_CMDLINE_CAP + 1} chars was accepted"

    at_cap = "b" * (WINDOWS_CMDLINE_CAP - len("c.exe") - 1)
    boundary = impl.build_argv(
        exe="c.exe", prompt="p", transport="stdin", flags=(at_cap,)
    )
    if boundary.cmdline_len != WINDOWS_CMDLINE_CAP:
        return (
            False,
            "control failed: the boundary case did not land exactly on the cap",
        )
    return (
        True,
        "40 KB routed off argv; an embedded prompt under the cap is still refused; "
        f"cap boundary exact at {WINDOWS_CMDLINE_CAP}",
    )


def r5_hardening_is_required_and_win_arg_limit_retries_once(
    impl: Impl,
) -> tuple[bool, str]:
    """R5 — ``--ignore-user-config`` on every non-interactive codex call; one retry only.

    MEASURED: the active MCP inventory is what blows the argv limit, so omitting that flag is
    the #1 execution blocker; and ``win-arg-limit`` must retry exactly once, never in a loop.
    """
    plan = impl.build_for_rail(
        CODEX_RAIL, prompt="do it", prompt_path="C:/tmp/r.txt", flags=("exec",)
    )
    if "--ignore-user-config" not in plan.argv:
        return False, "the rail's hardening flag was not injected"
    try:
        impl.build_for_rail(
            CODEX_RAIL,
            prompt="do it",
            prompt_path="C:/tmp/r.txt",
            inject_hardening=False,
        )
    except PolicyViolation:
        pass
    else:
        return False, "a codex invocation missing --ignore-user-config was accepted"

    first = impl.plan_retry("win-arg-limit", attempt=1)
    if not first.retry:
        return False, "win-arg-limit did not earn its one retry"
    if impl.plan_retry("win-arg-limit", attempt=first.next_attempt).retry:
        return False, "win-arg-limit retried more than once"
    if impl.plan_retry("severed-stream", attempt=1).retry:
        return False, "control failed: an unrelated reason was retried"
    return True, "hardening injected and verified; win-arg-limit retries exactly once"


def r6_no_dispatch_without_an_explicit_timeout(impl: Impl) -> tuple[bool, str]:
    """R6 — a dispatch with no timeout is refused before the rail is touched."""
    rail, plan = _rail(impl, ScriptedResponse(exit_code=0, receipt=GOOD_JSON))
    try:
        rail.dispatch(unit_id="u1", plan=plan, timeout_s=None, awaited=True)
    except DispatchRefused:
        pass
    else:
        return False, "the rail LAUNCHED a dispatch with no timeout"

    # As in R1: the rail exercise already covers the `timeout_s=None` predicate arm, so only the
    # shapes the rail did NOT exercise get their own assertion here.
    if "nonpositive-timeout" not in impl.check_dispatch(
        background=False, timeout_s=0, awaited=True
    ):
        return False, "the policy predicate accepted a zero timeout"
    if impl.check_dispatch(background=False, timeout_s=1800, awaited=True) != ():
        return False, "control failed: an explicit positive timeout was refused"
    return (
        True,
        "a missing or non-positive timeout is refused; an explicit one is accepted",
    )


def r8_the_dispatch_path_is_deterministic(impl: Impl) -> tuple[bool, str]:
    """R8 — two runs produce identical artifacts, and no clock/entropy is on the path."""
    if not impl.scan_source("import time\nx = time.time()\n", "fixture.py"):
        return False, "the determinism check stayed SILENT on a known-broken fixture"
    oracle_source = (
        Path(agentspec.__file__).with_name("oracle.py").read_text(encoding="utf-8")
    )
    leaks = impl.scan_source(oracle_source, "oracle.py")
    if leaks:
        return False, f"the dispatch path itself is non-deterministic: {leaks}"

    first, second = _one_run(impl), _one_run(impl)
    if first != second:
        return False, f"two identical runs diverged:\n  {first}\n  {second}"
    return True, "detector fires on a broken fixture; two runs are byte-identical"


def _one_run(impl: Impl) -> str:
    """One whole scripted dispatch, serialised. Deterministic by construction."""
    rail, plan = _rail(
        impl, ScriptedResponse(exit_code=0, receipt=GOOD_JSON, wall_ms_delta=1234)
    )
    result = rail.dispatch(unit_id="u1", plan=plan, timeout_s=1800, awaited=True)
    verdict = impl.judge("u1", result, JSON_SPEC)
    return impl.serialise(observe(verdict, artifacts=("out/u1.json",)))


def _rail(impl: Impl, *responses: ScriptedResponse) -> tuple[FakeRail, ArgvPlan]:
    """A fake rail wired to the INJECTED policy, so a mutant can make it launch the forbidden."""
    rail = FakeRail(
        script={"u1": responses}, clock=FixedClock(), policy=impl.check_dispatch
    )
    return rail, build_argv(exe="fake.exe", prompt="do it", transport="stdin")
