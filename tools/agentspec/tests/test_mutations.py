"""THE MUTATION GUARD — the both-states test applied to the eval suite itself.

100% coverage does not prove behaviour. The owner has the receipt: a suite was 15/15 green
while reverting DEFAULT_MIN_BYTES 1024->512 still passed, because every case passed the value
explicitly and the default was never exercised.

So for each regression row, this module swaps a deliberately-BROKEN implementation into the
injected ``Impl`` bundle and requires that row to go RED. A row that stays green under its own
mutant is protecting nothing. The mutant set is asserted to cover EVERY row id, so a new row
cannot ship without a mutant.

This runs entirely in-process — no subprocess, no patched temp copy of a module — so it is fast
and deterministic, and it fails for exactly one reason.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

import pytest

from agentspec.argv import (
    WINDOWS_CMDLINE_CAP,
    ArgvPlan,
    ArgvTooLong,
    PolicyViolation,
    PromptOnArgv,
    render_cmdline,
)
from agentspec.determinism import Finding
from agentspec.evals.impl import DEFAULT_IMPL, Impl
from agentspec.evals.registry import REGISTRY, row_ids, run_all, run_row
from agentspec.oracle import RailResult, Verdict
from agentspec.progress import BACKGROUND_PHRASES, ProgressLog, ResultText
from agentspec.retry import RetryDecision
from agentspec.spec import ReceiptSpec


def _row(row_id: str) -> Any:
    return next(row for row in REGISTRY if row.id == row_id)


# --- the mutants ---------------------------------------------------------------------------


def _blind_dispatch_policy(**_kw: Any) -> tuple[str, ...]:
    """M-R1/M-R6: the pre-dispatch policy always says OK."""
    return ()


def _exit_zero_is_success(
    unit_id: str, result: RailResult, _spec: ReceiptSpec
) -> Verdict:
    """M-R2a: the historical bug — exit 0 treated as completion."""
    return Verdict(
        unit_id=unit_id,
        ok=result.exit_code == 0,
        reason=None,
        severed=False,
        passed_clauses=(),
        detail="mutant: exit 0 is success",
    )


def _never_severed(unit_id: str, result: RailResult, spec: ReceiptSpec) -> Verdict:
    """M-R2b: the fine cause survives but the severed family flag is dropped."""
    verdict = DEFAULT_IMPL.judge(unit_id, result, spec)
    return dataclasses.replace(verdict, severed=False)


def _everything_is_a_result(payload: str) -> ResultText:
    """M-R3: the progress stream is accepted as a result."""
    return ResultText(text=payload)


def _uncapped_build_argv(**kwargs: Any) -> ArgvPlan:
    """M-R4: the Windows command-line cap is not enforced."""
    return DEFAULT_IMPL.build_argv(**{**kwargs, "cap": 10**9})


def _unhardened_build_for_rail(rail: Any, **kwargs: Any) -> ArgvPlan:
    """M-R5a: the hardening flags are neither injected nor verified."""
    stripped = dataclasses.replace(rail, hardening=())
    return DEFAULT_IMPL.build_for_rail(stripped, **kwargs)


def _retry_forever(reason: str, *, attempt: int) -> RetryDecision:
    """M-R5b: `win-arg-limit` retries without a bound."""
    return RetryDecision(
        retry=True,
        next_attempt=attempt + 1,
        reason=reason,
        rationale="mutant: retry forever",
    )


def _blind_scan(_source: str, _path: str) -> tuple[Any, ...]:
    """M-R8a: the determinism static check reports nothing."""
    return ()


def _nondeterministic_serialise(
    _state: dict[str, int] = {"n": 0},
) -> Callable[[Any], str]:
    """M-R8b: serialisation embeds a call counter, so two identical runs differ."""

    def serialise(obs: Any) -> str:
        _state["n"] += 1
        return f"{DEFAULT_IMPL.serialise(obs)}#{_state['n']}"

    return serialise


# --- targeted mutants, one per remaining sub-assertion in a row body ------------------------
#
# Coverage of `agentspec/evals/rows.py` is what forced these into existence: every `return
# False, ...` arm that no mutant reached showed up as an uncovered line, i.e. a sub-assertion
# nothing proved was load-bearing. Rather than exclude those lines, each got a mutant.


def _refuses_any_background(
    *, background: bool, timeout_s: int | None, awaited: bool
) -> tuple[str, ...]:
    """M-R1c: over-reach — refuses background even when nothing awaits the dispatch."""
    found = ["background-on-awaited-dispatch"] if background else []
    if timeout_s is None:
        found.append("missing-timeout")
    elif timeout_s <= 0:
        found.append("nonpositive-timeout")
    return tuple(sorted(found))


def _accepts_zero_timeout(
    *, background: bool, timeout_s: int | None, awaited: bool
) -> tuple[str, ...]:
    """M-R6b: refuses a MISSING timeout but accepts a non-positive one."""
    found = ["background-on-awaited-dispatch"] if background and awaited else []
    if timeout_s is None:
        found.append("missing-timeout")
    return tuple(sorted(found))


def _refuses_every_timeout(**_kw: Any) -> tuple[str, ...]:
    """M-R6c: over-reach — refuses an explicit, positive, perfectly valid timeout."""
    return ("nonpositive-timeout",)


def _fine_reason_only(verdict: Any) -> str:
    """M-R2c: drops `severed-stream` from the terminal line, breaking every consumer that
    matches on the family rather than the fine cause."""
    return f"FAILED:{verdict.unit_id} {verdict.failure_reason}"


def _always_severed_failure(
    unit_id: str, _result: RailResult, _spec: ReceiptSpec
) -> Verdict:
    """M-R2d: nothing ever succeeds, so the good-run control must fire."""
    return Verdict(
        unit_id=unit_id,
        ok=False,
        reason="receipt-missing",
        severed=True,
        passed_clauses=(),
        detail="mutant: always severed",
    )


def _phrase_detection_only(payload: str) -> Any:
    """M-R3b: keeps the background-phrase rule, loses the bare progress-stream rule."""
    lowered = payload.lower()
    for phrase in BACKGROUND_PHRASES:
        if phrase in lowered:
            return ProgressLog(text=payload, marker=phrase)
    return ResultText(text=payload)


def _everything_is_progress(payload: str) -> ProgressLog:
    """M-R3c: over-reach — a real answer is rejected as progress."""
    return ProgressLog(text=payload, marker="mutant")


def _prompt_on_argv_honest_length(**kwargs: Any) -> ArgvPlan:
    """M-R4b: puts the prompt on argv and reports the resulting (huge) length truthfully."""
    argv = (kwargs["exe"], kwargs["prompt"])
    return ArgvPlan(
        argv=argv,
        prompt_transport=kwargs["transport"],
        prompt_path=kwargs.get("prompt_path"),
        stdin_payload=None,
        cmdline_len=len(render_cmdline(argv)),
    )


def _prompt_on_argv_understated_length(**kwargs: Any) -> ArgvPlan:
    """M-R4c: puts the prompt on argv AND under-reports the length, so only the
    prompt-in-argv assertion can catch it."""
    return dataclasses.replace(_prompt_on_argv_honest_length(**kwargs), cmdline_len=10)


def _drops_stdin_payload(**kwargs: Any) -> ArgvPlan:
    """M-R4d: correct for the file transport, silently loses the stdin prompt."""
    return dataclasses.replace(DEFAULT_IMPL.build_argv(**kwargs), stdin_payload=None)


def _wrong_over_cap_reason(**kwargs: Any) -> ArgvPlan:
    """M-R4e: still refuses an over-cap command line, but not as `win-arg-limit`, so a caller
    cannot apply the one-retry policy."""
    try:
        return DEFAULT_IMPL.build_argv(**kwargs)
    except ArgvTooLong as exc:
        raise ValueError("command line too long") from exc


def _off_by_one_length(**kwargs: Any) -> ArgvPlan:
    """M-R4f: reports one char less than the truth, which is exactly how a cap boundary
    silently slips by."""
    plan = DEFAULT_IMPL.build_argv(**kwargs)
    return dataclasses.replace(plan, cmdline_len=plan.cmdline_len - 1)


def _hardening_cannot_be_skipped(rail: Any, **kwargs: Any) -> ArgvPlan:
    """M-R5c: injects hardening unconditionally, so the VERIFICATION is never exercised —
    a caller that strips the flag is accepted."""
    kwargs.pop("inject_hardening", None)
    return DEFAULT_IMPL.build_for_rail(rail, **kwargs)


def _never_retry(reason: str, *, attempt: int) -> RetryDecision:
    """M-R5d: win-arg-limit loses its one legitimate retry."""
    return RetryDecision(
        retry=False,
        next_attempt=attempt,
        reason=reason,
        rationale="mutant: never retry",
    )


def _retry_anything_once(reason: str, *, attempt: int) -> RetryDecision:
    """M-R5e: bounds the retry correctly but applies it to EVERY reason, so a severed stream
    gets silently re-run."""
    if attempt >= 2:
        return RetryDecision(
            retry=False, next_attempt=attempt, reason=reason, rationale="mutant: stop"
        )
    return RetryDecision(
        retry=True,
        next_attempt=attempt + 1,
        reason=reason,
        rationale="mutant: retry any once",
    )


def _embedded_prompt_allowed(**kwargs: Any) -> ArgvPlan:
    """M-R4g: rules 1 and 2 only — bare CONTAINMENT is dropped.

    This is the in-process equivalent of raising ``MIN_SUBSTRING_SCAN_LEN`` past the prompt
    length, which the adversarial critic MEASURED to be invisible to both the suite and the
    100% line+branch gate (2026-07-26). The prompt still cannot be passed as a bare argument
    or as ``--flag=<body>``, and the cap is still enforced, so ONLY an assertion about a prompt
    embedded in a LARGER argv element can catch this mutant.
    """
    prompt = kwargs["prompt"]
    argv = (kwargs["exe"], *tuple(kwargs.get("flags", ())))
    if kwargs.get("transport") == "file":
        argv = (*argv, kwargs["prompt_flag"], kwargs["prompt_path"])
    for element in argv:
        if element == prompt or any(
            element.endswith(delimiter + prompt) for delimiter in ("=", ":")
        ):
            raise PromptOnArgv("mutant: equality and delimiter rules only")
    cap = kwargs.get("cap", WINDOWS_CMDLINE_CAP)
    cmdline_len = len(render_cmdline(argv))
    if cmdline_len > cap:
        raise ArgvTooLong(cmdline_len=cmdline_len, cap=cap)
    return ArgvPlan(
        argv=argv,
        prompt_transport=kwargs["transport"],
        prompt_path=kwargs.get("prompt_path"),
        stdin_payload=prompt if kwargs.get("transport") == "stdin" else None,
        cmdline_len=cmdline_len,
    )


def _always_finds_a_leak(_source: str, path: str) -> tuple[Finding, ...]:
    """M-R8c: over-reach — reports the clean dispatch path as non-deterministic."""
    return (Finding(path=path, line=1, code="forbidden-import", detail="mutant"),)


MUTANTS: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "M-R1 pre-dispatch policy ignores --background",
        "R1",
        {"check_dispatch": _blind_dispatch_policy},
    ),
    (
        "M-R2a exit 0 alone is treated as SUCCESS",
        "R2",
        {"judge": _exit_zero_is_success},
    ),
    (
        "M-R2b the severed-stream family flag is dropped",
        "R2",
        {"judge": _never_severed},
    ),
    (
        "M-R3 the progress stream is accepted as a result",
        "R3",
        {"classify": _everything_is_a_result},
    ),
    (
        "M-R4 the Windows argv cap is not enforced",
        "R4",
        {"build_argv": _uncapped_build_argv},
    ),
    (
        "M-R5a --ignore-user-config is not required",
        "R5",
        {"build_for_rail": _unhardened_build_for_rail},
    ),
    (
        "M-R5b win-arg-limit retries without a bound",
        "R5",
        {"plan_retry": _retry_forever},
    ),
    (
        "M-R6 a missing timeout is not refused",
        "R6",
        {"check_dispatch": _blind_dispatch_policy},
    ),
    ("M-R8a the determinism check reports nothing", "R8", {"scan_source": _blind_scan}),
    (
        "M-R8b serialisation is non-deterministic",
        "R8",
        {"serialise": _nondeterministic_serialise()},
    ),
    # one per remaining sub-assertion, found by coverage of the row bodies
    (
        "M-R1c background refused even when UNawaited",
        "R1",
        {"check_dispatch": _refuses_any_background},
    ),
    (
        "M-R2c the terminal line drops severed-stream",
        "R2",
        {"terminal_line": _fine_reason_only},
    ),
    (
        "M-R2d a fully good run stops reporting SUCCESS",
        "R2",
        {"judge": _always_severed_failure},
    ),
    (
        "M-R3b the bare progress-stream rule is lost",
        "R3",
        {"classify": _phrase_detection_only},
    ),
    (
        "M-R3c a real answer is rejected as progress",
        "R3",
        {"classify": _everything_is_progress},
    ),
    (
        "M-R3d a progress body as the receipt reports SUCCESS",
        "R3",
        {"judge": _exit_zero_is_success},
    ),
    (
        "M-R4b the prompt is placed on argv",
        "R4",
        {"build_argv": _prompt_on_argv_honest_length},
    ),
    (
        "M-R4c the prompt is on argv and the length under-reported",
        "R4",
        {"build_argv": _prompt_on_argv_understated_length},
    ),
    (
        "M-R4d the stdin prompt is silently dropped",
        "R4",
        {"build_argv": _drops_stdin_payload},
    ),
    (
        "M-R4e over-cap is refused but not as win-arg-limit",
        "R4",
        {"build_argv": _wrong_over_cap_reason},
    ),
    (
        "M-R4f the reported command-line length is off by one",
        "R4",
        {"build_argv": _off_by_one_length},
    ),
    (
        "M-R4g a prompt EMBEDDED in a larger argv element is accepted",
        "R4",
        {"build_argv": _embedded_prompt_allowed},
    ),
    (
        "M-R5c hardening is injected but never verified",
        "R5",
        {"build_for_rail": _hardening_cannot_be_skipped},
    ),
    ("M-R5d win-arg-limit loses its one retry", "R5", {"plan_retry": _never_retry}),
    (
        "M-R5e every reason becomes retryable",
        "R5",
        {"plan_retry": _retry_anything_once},
    ),
    (
        "M-R6b a non-positive timeout is accepted",
        "R6",
        {"check_dispatch": _accepts_zero_timeout},
    ),
    (
        "M-R6c a valid explicit timeout is refused",
        "R6",
        {"check_dispatch": _refuses_every_timeout},
    ),
    (
        "M-R8c the clean dispatch path is reported as leaking",
        "R8",
        {"scan_source": _always_finds_a_leak},
    ),
)


# --- the guard -----------------------------------------------------------------------------


def test_every_row_is_green_in_the_UNMUTATED_state() -> None:
    """The other half of both-states: the mutants below mean nothing if this is red."""
    assert [o.row_id for o in run_all() if not o.passed] == []


@pytest.mark.parametrize(
    ("label", "row_id", "override"), MUTANTS, ids=[m[0] for m in MUTANTS]
)
def test_the_row_goes_RED_under_its_mutant(
    label: str, row_id: str, override: dict[str, Any]
) -> None:
    outcome = run_row(_row(row_id), impl=dataclasses.replace(DEFAULT_IMPL, **override))
    assert outcome.passed is False, (
        f"{label}: row {row_id} stayed GREEN under its mutant, so it protects nothing"
    )
    assert outcome.observation.status == "error"


def test_the_mutant_set_covers_every_row() -> None:
    """One mutation per mandated rule: a new row cannot ship unprotected."""
    assert {row_id for _label, row_id, _o in MUTANTS} == set(row_ids())


def test_mutant_labels_are_unique() -> None:
    labels = [label for label, _r, _o in MUTANTS]
    assert len(set(labels)) == len(labels)


def test_a_mutant_only_breaks_its_OWN_row_when_the_seam_is_row_specific() -> None:
    """Blast-radius control: the argv-cap mutant must not silently red an unrelated row.

    R1 (background policy) does not touch build_argv's cap, so it must stay green — otherwise
    the parametrised assertion above could be passing for the wrong reason.
    """
    mutated = dataclasses.replace(DEFAULT_IMPL, build_argv=_uncapped_build_argv)
    assert run_row(_row("R1"), impl=mutated).passed is True


def test_impl_is_frozen_so_a_mutant_cannot_leak_into_the_default() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        DEFAULT_IMPL.judge = _exit_zero_is_success  # type: ignore[misc]


def test_replacing_a_seam_returns_a_new_impl_and_leaves_the_default_intact() -> None:
    mutated = dataclasses.replace(DEFAULT_IMPL, judge=_exit_zero_is_success)
    assert isinstance(mutated, Impl)
    assert mutated.judge is not DEFAULT_IMPL.judge
    assert run_all()[1].passed is True


def test_the_policy_violation_type_is_what_the_hardening_row_relies_on() -> None:
    """Pins the coupling the R5 row asserts, so a rename cannot silently loosen it."""
    assert issubclass(PolicyViolation, ValueError)
    assert PolicyViolation.reason == "policy-violation"
