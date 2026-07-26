"""Mutation probe: revert each load-bearing decision and require detection.

100% line+branch coverage does NOT prove behaviour. The receipt this estate already
holds: a suite was 15/15 green while reverting a default from 1024 to 512 still passed,
because every case passed the value explicitly and the default was never exercised.

So each row below MUTATES one load-bearing decision in mcpctl and asserts that the
corresponding property check goes RED. A mutant that survives means the suite has
stopped protecting that decision, and this file fails -- which is the both-states
discipline applied to a test suite rather than to a probe.

This file lives in ``tests/`` on purpose: the ``gate-tests-coverage mcpctl`` step runs
the whole suite, so the probe is EXECUTED by CI rather than described in prose.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest

from mcpctl import envelope, matrix, render, resolve, safety, topology
from mcpctl.resolve import State
from mcpctl.scopes import ScopeId

FAKE_XAI = "xai-" + "B" * 40
FAKE_GEMINI = "AIza" + "C" * 35
FAKE_OPAQUE = "E" * 44
FAKE_GH_PAT = "ghp_" + "H" * 36


# --------------------------------------------------------------------------- checks
# Each check asserts ONE load-bearing behaviour. Unmutated they all pass (proved by
# test_every_check_passes_unmutated); mutated, each must raise AssertionError.


def check_xai_masked() -> None:
    assert FAKE_XAI not in safety.redact_text(f"k={FAKE_XAI}")


def check_google_masked() -> None:
    assert FAKE_GEMINI not in safety.redact_text(f"k={FAKE_GEMINI}")


def check_opaque_masked() -> None:
    assert FAKE_OPAQUE not in safety.redact_text(f"Authorization: Bearer {FAKE_OPAQUE}")


def check_home_collapsed() -> None:
    assert "bob" not in safety.redact_text("C:/Users/bob/x")


def check_controls_stripped() -> None:
    assert "\x1b" not in safety.strip_controls("a\x1b]52;c;x\x07b")


def check_env_value_never_captured() -> None:
    fields = safety.env_fields({"TOK": FAKE_GH_PAT})
    assert FAKE_GH_PAT not in repr(fields)


def check_env_reference_not_reported_as_present() -> None:
    (field,) = safety.env_fields({"TOK": "${TOK}"})
    assert field.kind == "reference"


def check_project_row_is_exact_never_ancestor() -> None:
    doc = {"projects": {"C:/work": {"disabledMcpServers": ["x"]}}}
    _row, found = topology.project_row(doc, "C:/work/deeper")
    assert found is False


def check_denied_list_reads_the_object_shape() -> None:
    assert topology.parse_denied_list([{"serverName": "m"}]) == ("m",)


def check_approval_does_not_override_a_disable() -> None:
    top = topology.build_topology(
        topology.SourceDocs(
            claude_json={
                "mcpServers": {"g": {"command": "x"}},
                "disabledMcpServers": ["g"],
            },
            mcp_json={"mcpServers": {"g": {"command": "x"}}},
            settings_local={"enabledMcpjsonServers": ["g"]},
        ),
        project_key=None,
    )
    assert resolve.resolve_topology(top)["g"].state is State.DISABLED


def check_denied_outranks_disabled() -> None:
    out = resolve.resolve_state(
        definitions=(ScopeId.CLAUDE_USER,),
        mentions=(ScopeId.SETTINGS_DENIED, ScopeId.CLAUDE_USER_DISABLED),
        approved=False,
        enable_all_project_servers=False,
    )
    assert out.state is State.DENIED


def check_loadout_template_decides_nothing() -> None:
    out = resolve.resolve_state(
        definitions=(ScopeId.CLAUDE_USER,),
        mentions=(ScopeId.LOADOUT_TEMPLATE,),
        approved=False,
        enable_all_project_servers=False,
    )
    assert out.state is State.ENABLED


def check_multi_scope_state_is_marked_inferred() -> None:
    out = resolve.resolve_state(
        definitions=(ScopeId.CLAUDE_USER,),
        mentions=(ScopeId.CLAUDE_PROJECT_DISABLED, ScopeId.CLAUDE_USER_DISABLED),
        approved=False,
        enable_all_project_servers=False,
    )
    assert out.inferred is True


def check_unmeasured_tool_count_renders_as_a_dash() -> None:
    top = topology.build_topology(
        topology.SourceDocs(claude_json={"mcpServers": {"a": {"command": "c"}}}),
        project_key=None,
    )
    line = render.render_matrix(matrix.build_rows(top, liveness={})).splitlines()[2]
    assert line.split()[3] == "-"


def check_last_error_is_redacted_on_the_row() -> None:
    top = topology.build_topology(
        topology.SourceDocs(claude_json={"mcpServers": {"a": {"command": "c"}}}),
        project_key=None,
    )
    (row,) = matrix.build_rows(
        top, liveness={"a": matrix.Liveness(last_error=f"boom {FAKE_GH_PAT}")}
    )
    assert row.last_error is not None
    assert FAKE_GH_PAT not in row.last_error


def check_error_envelope_requires_the_recovery_triple() -> None:
    # Deliberately NOT pytest.raises: it signals a miss with pytest's `Failed`, which
    # does not derive from AssertionError, so the harness below would not see it. Every
    # check in this file must report a miss as AssertionError and nothing else.
    try:
        envelope.error("boom", root_cause="", retry="r", stop_condition="s")
    except ValueError:
        return
    raise AssertionError("error() accepted a blank root_cause")


def check_terminal_line_marks_an_error_as_failed() -> None:
    bad = envelope.error("boom", root_cause="c", retry="r", stop_condition="s")
    assert envelope.terminal_line("u", bad).startswith("FAILED:u")


# ------------------------------------------------------------------------- mutants


def _drop_pattern(needle: str) -> Callable[[pytest.MonkeyPatch], None]:
    def _apply(mp: pytest.MonkeyPatch) -> None:
        kept = tuple(
            (pat, rep)
            for pat, rep in safety._SECRET_PATTERNS
            if needle not in pat.pattern
        )
        assert len(kept) < len(safety._SECRET_PATTERNS), (
            f"mutation is inert: no shipped pattern contains {needle!r}"
        )
        mp.setattr(safety, "_SECRET_PATTERNS", kept)
        mp.setattr(safety, "_REDACT", safety.make_redactor(None))

    return _apply


def _mutate_home_regex(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(safety, "_HOME_RE", re.compile(r"(?!x)x"))
    mp.setattr(safety, "_REDACT", safety.make_redactor(None))


def _mutate_strip_to_identity(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(safety, "_STRIP", lambda s: s)


def _mutate_env_fields_to_leak_the_value(mp: pytest.MonkeyPatch) -> None:
    def leaking(env: object) -> tuple[safety.EnvField, ...]:
        if not isinstance(env, dict):
            return ()
        return tuple(safety.EnvField(name=k, kind=str(v)) for k, v in env.items())

    mp.setattr(safety, "env_fields", leaking)
    mp.setattr(topology, "env_fields", leaking)


def _mutate_env_reference_to_present(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        safety,
        "env_fields",
        lambda env: tuple(safety.EnvField(name=k, kind="present") for k in (env or {})),
    )


def _mutate_project_row_to_walk_ancestors(mp: pytest.MonkeyPatch) -> None:
    def ancestor_row(doc: object, key: str | None):
        if key is None or not isinstance(doc, dict):
            return {}, False
        projects = doc.get("projects") or {}
        for candidate in projects:
            if key.replace("\\", "/").startswith(candidate):
                return projects[candidate], True
        return {}, False

    mp.setattr(topology, "project_row", ancestor_row)


def _mutate_denied_list_to_strings_only(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(topology, "parse_denied_list", topology.parse_name_list)


def _mutate_approval_to_override_a_disable(mp: pytest.MonkeyPatch) -> None:
    original = resolve.resolve_state

    def approving(**kwargs: object):
        if kwargs.get("approved"):
            return resolve.Resolution(state=State.ENABLED)
        return original(**kwargs)  # type: ignore[arg-type]

    mp.setattr(resolve, "resolve_state", approving)


def _mutate_precedence_to_put_disabled_first(mp: pytest.MonkeyPatch) -> None:
    def disabled_first(**kwargs: object):
        mentions = kwargs.get("mentions") or ()
        if ScopeId.CLAUDE_USER_DISABLED in mentions:  # type: ignore[operator]
            return resolve.Resolution(
                state=State.DISABLED, basis=(ScopeId.CLAUDE_USER_DISABLED,)
            )
        return resolve.Resolution(state=State.ENABLED)

    mp.setattr(resolve, "resolve_state", disabled_first)


def _mutate_loadout_to_decide(mp: pytest.MonkeyPatch) -> None:
    original = resolve.resolve_state

    def loadout_decides(**kwargs: object):
        mentions = kwargs.get("mentions") or ()
        if ScopeId.LOADOUT_TEMPLATE in mentions:  # type: ignore[operator]
            return resolve.Resolution(state=State.DISABLED)
        return original(**kwargs)  # type: ignore[arg-type]

    mp.setattr(resolve, "resolve_state", loadout_decides)


def _mutate_inferred_to_always_false(mp: pytest.MonkeyPatch) -> None:
    original = resolve.resolve_state

    def never_inferred(**kwargs: object):
        out = original(**kwargs)  # type: ignore[arg-type]
        return resolve.Resolution(
            state=out.state, basis=out.basis, conflicts=out.conflicts, inferred=False
        )

    mp.setattr(resolve, "resolve_state", never_inferred)


def _mutate_unmeasured_tool_count_to_zero(mp: pytest.MonkeyPatch) -> None:
    original = matrix.build_rows

    def zeroing(top: object, *, liveness: object):
        rows = original(top, liveness=liveness)  # type: ignore[arg-type]
        return tuple(
            matrix.Row(
                **{
                    **{f: getattr(r, f) for f in r.__dataclass_fields__},
                    "tool_count": 0 if r.tool_count is None else r.tool_count,
                }
            )
            for r in rows
        )

    mp.setattr(matrix, "build_rows", zeroing)


def _mutate_row_last_error_to_raw(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(matrix, "safe", lambda s: s)


def _mutate_error_envelope_to_accept_blanks(mp: pytest.MonkeyPatch) -> None:
    def lax(summary: str, **kwargs: object):
        return envelope.Envelope(
            status="error",
            summary=summary,
            next_actions=("x",),
            root_cause=str(kwargs.get("root_cause", "")),
            retry=str(kwargs.get("retry", "")),
            stop_condition=str(kwargs.get("stop_condition", "")),
        )

    mp.setattr(envelope, "error", lax)


def _mutate_terminal_line_to_always_succeed(mp: pytest.MonkeyPatch) -> None:
    mp.setattr(
        envelope, "terminal_line", lambda unit, env: f"SUCCESS:{unit} {env.summary}"
    )


#: (mutant id, apply-the-mutation, the check that MUST go red)
MUTANTS: tuple[
    tuple[str, Callable[[pytest.MonkeyPatch], None], Callable[[], None]], ...
] = (
    ("drop-xai-pattern", _drop_pattern("xai-"), check_xai_masked),
    ("drop-google-pattern", _drop_pattern("AIza"), check_google_masked),
    ("drop-opaque-pattern", _drop_pattern("authorization"), check_opaque_masked),
    ("neuter-home-collapse", _mutate_home_regex, check_home_collapsed),
    ("strip-controls-identity", _mutate_strip_to_identity, check_controls_stripped),
    (
        "env-fields-leak-value",
        _mutate_env_fields_to_leak_the_value,
        check_env_value_never_captured,
    ),
    (
        "env-reference-as-present",
        _mutate_env_reference_to_present,
        check_env_reference_not_reported_as_present,
    ),
    (
        "project-row-ancestor-walk",
        _mutate_project_row_to_walk_ancestors,
        check_project_row_is_exact_never_ancestor,
    ),
    (
        "denied-list-strings-only",
        _mutate_denied_list_to_strings_only,
        check_denied_list_reads_the_object_shape,
    ),
    (
        "approval-overrides-disable",
        _mutate_approval_to_override_a_disable,
        check_approval_does_not_override_a_disable,
    ),
    (
        "disabled-outranks-denied",
        _mutate_precedence_to_put_disabled_first,
        check_denied_outranks_disabled,
    ),
    (
        "loadout-template-decides",
        _mutate_loadout_to_decide,
        check_loadout_template_decides_nothing,
    ),
    (
        "inferred-always-false",
        _mutate_inferred_to_always_false,
        check_multi_scope_state_is_marked_inferred,
    ),
    (
        "unmeasured-tools-as-zero",
        _mutate_unmeasured_tool_count_to_zero,
        check_unmeasured_tool_count_renders_as_a_dash,
    ),
    (
        "row-last-error-raw",
        _mutate_row_last_error_to_raw,
        check_last_error_is_redacted_on_the_row,
    ),
    (
        "error-envelope-accepts-blanks",
        _mutate_error_envelope_to_accept_blanks,
        check_error_envelope_requires_the_recovery_triple,
    ),
    (
        "terminal-always-success",
        _mutate_terminal_line_to_always_succeed,
        check_terminal_line_marks_an_error_as_failed,
    ),
)


def test_every_check_passes_unmutated():
    """Control: without a mutation every check must be GREEN.

    Without this, a check that is broken outright would 'detect' every mutant and the
    probe would report success while measuring nothing.
    """
    for mutant_id, _apply, check in MUTANTS:
        check()  # must not raise
        assert mutant_id


@pytest.mark.parametrize(
    ("mutant_id", "apply_mutation", "check"),
    MUTANTS,
    ids=[m[0] for m in MUTANTS],
)
def test_each_mutant_is_detected(
    mutant_id: str,
    apply_mutation: Callable[[pytest.MonkeyPatch], None],
    check: Callable[[], None],
    monkeypatch: pytest.MonkeyPatch,
):
    apply_mutation(monkeypatch)
    with pytest.raises(AssertionError):
        check()


def test_the_mutant_set_covers_every_module_with_a_load_bearing_decision():
    """Guards against the set quietly shrinking to the easy modules."""
    assert len(MUTANTS) >= 17
    assert len({m[0] for m in MUTANTS}) == len(MUTANTS), "duplicate mutant id"
