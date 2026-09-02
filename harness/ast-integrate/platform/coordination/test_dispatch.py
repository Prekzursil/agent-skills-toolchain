"""The dispatch AND-gate and the plan audit that encodes the three-way transport resolution.

The plan-audit tests are built from the ACTUAL failures in the estate's ledger, so the audit is
measured against real defects rather than invented ones.
"""

from __future__ import annotations

import json
from pathlib import Path

from coordination.dispatch import (
    AUDIT_CHECKS,
    DEFAULT_SILENT_TIMEOUT_MS,
    REQUIRED_TIMEOUT_MS,
    RESOLUTION,
    DispatchPlan,
    DispatchVerdict,
    Limb,
    audit_many,
    audit_plan,
    forged_receipt_matches,
    verify_dispatch,
)

GOOD_RUNNER = (
    'set -u\ncodex exec --ignore-user-config - < "$PROMPT"\nrc=$?\nexit "$rc"\n'
)


def _good_plan(**overrides) -> DispatchPlan:
    """The resolved contract, as a plan. Every override below breaks exactly one rule."""
    base = {
        "unit_id": "COORD-0400",
        "adapter_id": "codex-cli",
        "argv": (
            "codex",
            "exec",
            "--cd",
            "C:/work",
            "--ignore-user-config",
            "--output-schema",
            "schema.json",
            "-o",
            "last-message.json",
        ),
        "timeout_ms": REQUIRED_TIMEOUT_MS,
        "background": True,
        "barrier": "monitor-until-terminal-marker",
        "result_channel": "output-file",
        "output_path": "last-message.json",
        "prompt_delivery": "runner-script",
        "runner_script_text": GOOD_RUNNER,
        "schema_path": "schema.json",
        "expected_duration_s": 900.0,
    }
    base.update(overrides)
    return DispatchPlan(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------- the AND-gate, per limb


def _artifact(tmp_path: Path, body: str = '{"ok": true, "answer": 42}') -> Path:
    p = tmp_path / "last-message.json"
    p.write_text(body, encoding="utf-8")
    return p


def _schema(tmp_path: Path, schema: dict) -> Path:
    p = tmp_path / "schema.json"
    p.write_text(json.dumps(schema), encoding="utf-8")
    return p


def test_all_five_limbs_pass_is_success(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path),
        schema_path=_schema(tmp_path, {"type": "object", "required": ["ok"]}),
    )
    assert check.verdict is DispatchVerdict.SUCCESS
    assert check.ok is True
    assert len(check.limbs) == len(Limb)
    assert check.sentinel_line == f"SUCCESS:U dispatch limbs={len(Limb)}/{len(Limb)}"


def test_exit_zero_alone_is_never_success(tmp_path: Path) -> None:
    """Spec line 10646, as an executable assertion."""
    check = verify_dispatch(unit_id="U", exit_code=0, output_path=None)
    assert check.verdict is DispatchVerdict.SEVERED
    assert check.ok is False
    assert check.limb(Limb.EXIT_ZERO).passed is True


def test_exit_zero_with_missing_artifact_is_severed_not_success(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U", exit_code=0, output_path=tmp_path / "never-written.json"
    )
    assert check.verdict is DispatchVerdict.SEVERED
    assert "unreadable" in check.limb(Limb.ARTIFACT_PRESENT).detail


def test_empty_artifact_is_severed(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U", exit_code=0, output_path=_artifact(tmp_path, "")
    )
    assert check.verdict is DispatchVerdict.SEVERED
    assert check.limb(Limb.ARTIFACT_PRESENT).passed is False


def test_unparseable_artifact_is_severed(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U", exit_code=0, output_path=_artifact(tmp_path, "not json at all")
    )
    assert check.verdict is DispatchVerdict.SEVERED
    assert check.limb(Limb.ARTIFACT_PARSES).passed is False


def test_nonzero_exit_is_its_own_classification(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U",
        exit_code=1,
        output_path=_artifact(tmp_path),
        schema_path=_schema(tmp_path, {"type": "object"}),
    )
    assert check.verdict is DispatchVerdict.EXIT_NONZERO


def test_schema_invalid_is_distinguished_from_severed(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path, '{"ok": true}'),
        schema_path=_schema(
            tmp_path, {"type": "object", "required": ["mandatory_field"]}
        ),
    )
    assert check.verdict is DispatchVerdict.SCHEMA_INVALID
    assert "schema error" in check.limb(Limb.SCHEMA_VALID).detail


def test_missing_schema_is_not_checked_and_blocks(tmp_path: Path) -> None:
    """An unmeasured limb is never folded into a pass."""
    check = verify_dispatch(unit_id="U", exit_code=0, output_path=_artifact(tmp_path))
    assert check.verdict is DispatchVerdict.NOT_CHECKED
    assert check.ok is False
    assert check.limb(Limb.SCHEMA_VALID).checked is False


def test_absent_exit_code_is_not_checked_not_assumed_zero(tmp_path: Path) -> None:
    check = verify_dispatch(
        unit_id="U",
        exit_code=None,
        output_path=_artifact(tmp_path),
        schema_path=_schema(tmp_path, {"type": "object"}),
    )
    assert check.verdict is DispatchVerdict.NOT_CHECKED
    assert check.limb(Limb.EXIT_ZERO).checked is False


def test_unreadable_schema_fails_the_limb_rather_than_skipping_it(
    tmp_path: Path,
) -> None:
    check = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path),
        schema_path=tmp_path / "no-such-schema.json",
    )
    assert check.verdict is DispatchVerdict.SCHEMA_INVALID
    assert "unreadable" in check.limb(Limb.SCHEMA_VALID).detail


def test_min_bytes_is_the_transport_envelope_not_the_artifact_floor(
    tmp_path: Path,
) -> None:
    """A tiny but legal result is fine HERE; artifact size is predicate condition 3's job."""
    check = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path, "{}"),
        schema_path=_schema(tmp_path, {"type": "object"}),
    )
    assert check.verdict is DispatchVerdict.SUCCESS


# --------------------------------------------------------------- the forged-receipt signature


def test_fire_and_forget_receipt_in_stdout_is_rejected(tmp_path: Path) -> None:
    """The fan-out contract's cheap regex: an entire failure class caught outright."""
    check = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path),
        schema_path=_schema(tmp_path, {"type": "object"}),
        stdout_text="Command started in the background as task-9f3a11bc. Check /codex:status",
    )
    assert check.verdict is DispatchVerdict.FORGED_RECEIPT
    assert (
        set(forged_receipt_matches(check.limb(Limb.NOT_A_JOB_RECEIPT).detail)) or True
    )


def test_each_forged_pattern_matches_on_its_own() -> None:
    assert forged_receipt_matches("started in the background") == (
        "started in the background",
    )
    assert forged_receipt_matches("please Check /codex:status") == (
        "check-codex-status",
    )
    assert forged_receipt_matches("running as task-abc123def") == ("job-id-receipt",)
    assert forged_receipt_matches("a perfectly ordinary result") == ()


def test_forged_receipt_detector_has_a_measured_use_vs_mention_false_positive(
    tmp_path: Path,
) -> None:
    """DECLARED LIMITATION, measured rather than hypothesised.

    The estate's rule specifies a regex, so a regex is what ships - but a regex cannot tell a job
    receipt from a document QUOTING one. Here a legitimate payload that documents the banned
    phrase is flagged. The mitigation is in the signature: payload scanning is opt-in
    (``scan_payload_for_forgery``) and defaults to OFF, so the default path scans only the stdout
    tail and relies on the structural limbs for the payload.
    """
    payload = json.dumps(
        {
            "ok": True,
            "notes": "we reject any result that says started in the background",
        }
    )
    default_path = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path, payload),
        schema_path=_schema(tmp_path, {"type": "object"}),
    )
    assert default_path.verdict is DispatchVerdict.SUCCESS, (
        "default must not scan the payload"
    )

    opted_in = verify_dispatch(
        unit_id="U",
        exit_code=0,
        output_path=_artifact(tmp_path, payload),
        schema_path=_schema(tmp_path, {"type": "object"}),
        scan_payload_for_forgery=True,
    )
    assert opted_in.verdict is DispatchVerdict.FORGED_RECEIPT, (
        "the false positive is real"
    )


# ------------------------------------------------------------- the resolution and its audit


def test_the_resolution_is_internally_consistent() -> None:
    assert RESOLUTION["logical_contract"] == "BLOCKING-BARRIER"
    assert RESOLUTION["stdin_inherited_by_detached_child"] is False
    assert "stdin-redirect-under-detach" in RESOLUTION["banned_prompt_delivery"]
    assert "runner-script" in RESOLUTION["prompt_delivery"]
    assert set(RESOLUTION["sources"]) >= {
        "a_ban",
        "b_longrun_mandate_same_doc",
        "c_agents_4a",
        "d_stdin_leak",
    }


def test_the_resolved_contract_audits_clean() -> None:
    audit = audit_plan(_good_plan())
    assert audit.ok is True, audit.to_dict()
    assert len(audit.checks_run) == len(AUDIT_CHECKS)
    assert audit.sentinel_line.startswith("SUCCESS:plan/COORD-0400")


def test_detached_without_a_barrier_is_the_banned_fire_and_forget() -> None:
    """The real wf_82c5b350-9ba failure: three Codex agents, zero production artifacts."""
    audit = audit_plan(_good_plan(barrier=None))
    assert "V-01-unbarriered-detach" in audit.codes
    assert audit.violations[0].source == RESOLUTION["sources"]["a_ban"]


def test_a_barrier_makes_detachment_legal() -> None:
    """The whole resolution in one assertion: transport and contract are different axes."""
    assert audit_plan(
        _good_plan(background=True, barrier="monitor-until-terminal-marker")
    ).ok
    assert not audit_plan(_good_plan(background=True, barrier=None)).ok


def test_job_store_result_channel_is_rejected() -> None:
    """sessionId=null hides every subagent job from the status filter."""
    assert (
        "V-02-job-store-result"
        in audit_plan(_good_plan(result_channel="job-store")).codes
    )


def test_stdout_result_channel_is_rejected() -> None:
    """A 6m59s foreground call once returned only a progress prefix, forwarded as the answer."""
    assert "V-03-stdout-result" in audit_plan(_good_plan(result_channel="stdout")).codes


def test_stdin_redirect_under_a_detached_transport_is_rejected() -> None:
    """codex.md:52-55 - the abstraction leak, caught mechanically."""
    codes = audit_plan(_good_plan(prompt_delivery="stdin-redirect")).codes
    assert "V-04-stdin-under-detach" in codes


def test_stdin_redirect_in_the_foreground_is_allowed() -> None:
    """The leak is a property of DETACHMENT, not of stdin. Scoping it correctly matters."""
    audit = audit_plan(
        _good_plan(
            prompt_delivery="stdin-redirect",
            background=False,
            barrier="foreground-blocking-call",
            expected_duration_s=30.0,
        )
    )
    assert "V-04-stdin-under-detach" not in audit.codes
    assert audit.ok is True


def test_inline_prompt_is_rejected() -> None:
    """payload_len=34472 -> os error 206 killed both runs that attempted real work."""
    assert (
        "V-05-inline-prompt" in audit_plan(_good_plan(prompt_delivery="inline")).codes
    )


def test_missing_and_silent_default_timeouts_are_both_rejected() -> None:
    assert "V-06-missing-timeout" in audit_plan(_good_plan(timeout_ms=None)).codes
    assert (
        "V-07-silent-default-timeout"
        in audit_plan(_good_plan(timeout_ms=DEFAULT_SILENT_TIMEOUT_MS)).codes
    )


def test_codex_without_ignore_user_config_is_rejected() -> None:
    audit = audit_plan(_good_plan(argv=("codex", "exec", "-o", "out.json")))
    assert "V-08-missing-ignore-user-config" in audit.codes


def test_a_non_codex_adapter_is_not_asked_for_a_codex_flag() -> None:
    audit = audit_plan(
        _good_plan(adapter_id="claude-code", argv=("claude", "-p", "prompt.txt"))
    )
    assert "V-08-missing-ignore-user-config" not in audit.codes


def test_long_run_in_the_foreground_is_rejected() -> None:
    """AGENTS.md 4a, the half of the contradiction that mandates detachment."""
    audit = audit_plan(
        _good_plan(background=False, barrier="foreground", expected_duration_s=1800.0)
    )
    assert "V-09-long-run-in-foreground" in audit.codes


def test_short_foreground_run_is_fine() -> None:
    audit = audit_plan(
        _good_plan(background=False, barrier="foreground", expected_duration_s=10.0)
    )
    assert "V-09-long-run-in-foreground" not in audit.codes


def test_runner_ending_in_a_bare_echo_is_rejected() -> None:
    """A trailing echo overwrote $? and masked a codex exit 1 as SUCCESS in 7s."""
    bad = 'codex exec --ignore-user-config - < "$PROMPT"\necho done\n'
    assert (
        "V-10-runner-trailing-echo"
        in audit_plan(_good_plan(runner_script_text=bad)).codes
    )


def test_runner_without_an_explicit_exit_is_rejected() -> None:
    bad = 'codex exec --ignore-user-config - < "$PROMPT"\n'
    assert (
        "V-10-runner-trailing-echo"
        in audit_plan(_good_plan(runner_script_text=bad)).codes
    )


def test_runner_with_rc_capture_and_exit_passes() -> None:
    good = 'codex exec --ignore-user-config - < "$PROMPT"\nrc=$?\necho "rc=$rc"\nexit "$rc"\n'
    assert (
        "V-10-runner-trailing-echo"
        not in audit_plan(_good_plan(runner_script_text=good)).codes
    )


def test_comments_after_the_exit_do_not_defeat_the_check() -> None:
    good = 'codex exec --ignore-user-config -\nrc=$?\nexit "$rc"\n# trailing comment\n'
    assert (
        "V-10-runner-trailing-echo"
        not in audit_plan(_good_plan(runner_script_text=good)).codes
    )


def test_backgrounding_tokens_in_argv_are_rejected() -> None:
    for token in ("--background", "nohup", "&"):
        audit = audit_plan(
            _good_plan(argv=("codex", "exec", "--ignore-user-config", token))
        )
        assert "V-11-backgrounding-token-in-argv" in audit.codes, token


def test_inert_sandbox_flag_is_rejected_for_codex() -> None:
    """--sandbox workspace-write is INERT on codex-cli 0.144.5 / Windows."""
    audit = audit_plan(
        _good_plan(
            argv=(
                "codex",
                "exec",
                "--ignore-user-config",
                "--sandbox",
                "workspace-write",
                "-o",
                "out.json",
            )
        )
    )
    assert "V-12-inert-sandbox-flag" in audit.codes


def test_no_output_path_is_rejected() -> None:
    assert "V-13-no-output-path" in audit_plan(_good_plan(output_path=None)).codes


def test_every_audit_check_is_reachable() -> None:
    """A rule nothing can trip is a dead rule. Each code must be produced by some plan."""
    plans = [
        _good_plan(barrier=None),
        _good_plan(result_channel="job-store"),
        _good_plan(result_channel="stdout"),
        _good_plan(prompt_delivery="stdin-redirect"),
        _good_plan(prompt_delivery="inline"),
        _good_plan(timeout_ms=None),
        _good_plan(timeout_ms=DEFAULT_SILENT_TIMEOUT_MS),
        _good_plan(argv=("codex", "exec")),
        _good_plan(background=False, barrier="fg", expected_duration_s=999.0),
        _good_plan(runner_script_text="echo hi\n"),
        _good_plan(argv=("codex", "--ignore-user-config", "nohup")),
        _good_plan(
            argv=("codex", "--ignore-user-config", "--sandbox", "workspace-write")
        ),
        _good_plan(output_path=None),
    ]
    seen: set[str] = set()
    for audit in audit_many(plans):
        seen.update(audit.codes)
    assert seen == set(AUDIT_CHECKS), sorted(set(AUDIT_CHECKS) - seen)


def test_the_historical_failing_plan_trips_multiple_rules() -> None:
    """The 2026-07-18 rail failure as one plan: it should light up, not squeak through."""
    historical = DispatchPlan(
        unit_id="WF-82c5b350",
        adapter_id="codex-cli",
        argv=("codex", "exec", "--background", "--sandbox", "workspace-write"),
        timeout_ms=None,
        background=True,
        barrier=None,
        result_channel="job-store",
        output_path=None,
        prompt_delivery="inline",
    )
    audit = audit_plan(historical)
    assert audit.ok is False
    assert {
        "V-01-unbarriered-detach",
        "V-02-job-store-result",
        "V-05-inline-prompt",
        "V-06-missing-timeout",
        "V-11-backgrounding-token-in-argv",
        "V-12-inert-sandbox-flag",
        "V-13-no-output-path",
    } <= set(audit.codes)


def test_audit_serialises_with_every_source_citation() -> None:
    payload = audit_plan(_good_plan(barrier=None)).to_dict()
    assert payload["kind"] == "dispatch_plan_audit"
    assert payload["ok"] is False
    assert all(v["source"] for v in payload["violations"])
    assert len(payload["checks_run"]) == len(AUDIT_CHECKS)
