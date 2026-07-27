"""The CLI: one envelope shape on every path, and no way to put a prompt on argv."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest
from agentspec.clock import FixedClock
from agentspec.envelope import ENVELOPE_FIELDS

from agentrail import cli
from agentrail.deploy import SHIM_NAME
from agentrail.ports import SpawnOutcome
from agentrail.runner import Ports
from fakes import FakeFileSystem, FakeSpawn

CONFIG = "/cfg/rails.toml"
HOME = "/home/u"
EXE = "/home/u/bin/demo"
PROMPT_FILE = "/in/prompt.txt"

RAILS_TOML = """
config_version = "1"

[rail.demo]
exe_globs = ["${HOME}/bin/*"]
native_transport = "stdin"
receipt_format = "text"
receipt_forbidden_markers = ["still in progress"]
verified = true

[rail.spilly]
exe_globs = ["${HOME}/bin/*"]
native_transport = "argv"
prompt_flag = "--prompt-file"
receipt_format = "text"
receipt_forbidden_markers = ["still in progress"]
verified = true

[rail.shaky]
exe_globs = ["${HOME}/bin/*"]
native_transport = "stdin"
receipt_format = "text"
receipt_forbidden_markers = ["still in progress"]
verified = false
notes = "UNVERIFIED: --version timed out at 15s"
"""


class Recorder:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)

    def payload(self) -> dict[str, object]:
        return json.loads(self.lines[-1])


def environment(
    *,
    files: dict[str, bytes] | None = None,
    outcomes: Sequence[SpawnOutcome] = (),
    stdin_text: str = "",
) -> tuple[cli.Environment, Recorder, FakeSpawn, FakeFileSystem]:
    fs = FakeFileSystem(
        {
            CONFIG: RAILS_TOML.encode("utf-8"),
            EXE: b"",
            PROMPT_FILE: b"do the thing",
            **(files or {}),
        }
    )
    spawn = FakeSpawn(list(outcomes))
    out = Recorder()
    env = cli.Environment(
        ports=Ports(fs=fs, spawn=spawn, clock=FixedClock()),
        home=HOME,
        tools_dir="/tools",
        config_path=CONFIG,
        out=out,
        stdin_text=lambda: stdin_text,
    )
    return env, out, spawn, fs


def run(argv: Sequence[str], **kwargs: object) -> tuple[int, dict[str, object]]:
    env, out, _, _ = environment(**kwargs)  # pyright: ignore[reportArgumentType]
    code = cli.main(list(argv), env=env)
    return code, out.payload()


def assert_enveloped(payload: dict[str, object]) -> None:
    for field in ENVELOPE_FIELDS:
        assert field in payload, f"{field} missing"
    assert payload["summary"]
    assert payload["next_actions"], "error-only output without next steps is banned"
    assert payload["terminal"]
    if payload["status"] == "error":
        detail = payload["error"]
        assert isinstance(detail, dict)
        for field in ("code", "root_cause", "retry_instruction", "stop_condition"):
            assert detail[field]


# --------------------------------------------------------------------------------------------
# rails / resolve
# --------------------------------------------------------------------------------------------


def test_rails_lists_every_row_and_marks_the_unverified_ones() -> None:
    code, payload = run(["rails"])
    assert code == cli.EXIT_OK
    assert_enveloped(payload)
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, list)
    assert any("demo [verified]" in item for item in artifacts)
    assert any("shaky [UNVERIFIED]" in item for item in artifacts)
    assert "2 verified, 1 UNVERIFIED" in str(payload["summary"])


def test_resolve_reports_the_dynamically_resolved_executable() -> None:
    code, payload = run(["resolve", "demo"])
    assert code == cli.EXIT_OK
    assert f"exe={EXE}" in payload["artifacts"]  # pyright: ignore[reportOperatorIssue]
    assert "glob-matches=1" in payload["artifacts"]  # pyright: ignore[reportOperatorIssue]


def test_resolve_warns_rather_than_succeeding_silently_on_a_fallback() -> None:
    toml = RAILS_TOML.replace(
        '[rail.demo]\nexe_globs = ["${HOME}/bin/*"]',
        '[rail.demo]\nexe_globs = ["${HOME}/vendor/*/demo"]\n'
        'exe_fallbacks = ["${HOME}/bin/demo"]',
    )
    code, payload = run(["resolve", "demo"], files={CONFIG: toml.encode("utf-8")})
    assert code == cli.EXIT_OK
    assert payload["status"] == "warning"
    assert_enveloped(payload)


def test_resolve_of_an_absent_executable_is_enveloped() -> None:
    env, out, _, fs = environment()
    del fs.files[EXE]
    assert cli.main(["resolve", "demo"], env=env) == cli.EXIT_ERROR
    payload = out.payload()
    assert_enveloped(payload)
    assert payload["terminal"] == "FAILED:demo env-missing"


# --------------------------------------------------------------------------------------------
# plan / run
# --------------------------------------------------------------------------------------------


def test_plan_builds_a_dispatch_without_spawning_anything() -> None:
    env, out, spawn, _ = environment()
    code = cli.main(
        ["plan", "demo", "--unit-id", "u1", "--prompt-file", PROMPT_FILE], env=env
    )
    assert code == cli.EXIT_OK
    assert spawn.calls == []
    assert_enveloped(out.payload())


def test_plan_records_the_spill_for_an_argv_native_rail() -> None:
    code, payload = run(
        ["plan", "spilly", "--unit-id", "u1", "--prompt-file", PROMPT_FILE]
    )
    joined = " | ".join(payload["artifacts"])  # pyright: ignore[reportCallIssue, reportArgumentType]
    assert "spilled-from=argv->file" in joined
    assert "do the thing" not in joined, "the prompt must never reach an argv rendering"
    assert code == cli.EXIT_OK


def test_run_dispatches_and_judges_the_receipt() -> None:
    env, out, spawn, _ = environment(
        outcomes=[SpawnOutcome(exit_code=0, stdout=b"3 files changed")]
    )
    code = cli.main(
        ["run", "demo", "--unit-id", "u1", "--prompt-file", PROMPT_FILE], env=env
    )
    assert code == cli.EXIT_OK
    payload = out.payload()
    assert payload["terminal"] == "SUCCESS:u1"
    assert spawn.calls[0]["stdin_payload"] == "do the thing"
    assert_enveloped(payload)


def test_run_forwards_cwd_timeout_and_extra_flags() -> None:
    env, _, spawn, _ = environment(outcomes=[SpawnOutcome(exit_code=0, stdout=b"ok")])
    cli.main(
        [
            "run",
            "demo",
            "--unit-id",
            "u1",
            "--prompt-file",
            PROMPT_FILE,
            "--cwd",
            "/work",
            "--timeout-s",
            "30",
            "--flag=--extra",
        ],
        env=env,
    )
    assert spawn.calls[0]["cwd"] == "/work"
    assert spawn.calls[0]["timeout_s"] == 30
    assert "--extra" in spawn.calls[0]["argv"]  # pyright: ignore[reportOperatorIssue]


def test_run_reports_a_severed_stream_as_a_failure() -> None:
    env, out, _, _ = environment(
        outcomes=[SpawnOutcome(exit_code=0, stdout=b"the job is still in progress")]
    )
    assert (
        cli.main(
            ["run", "demo", "--unit-id", "u1", "--prompt-file", PROMPT_FILE], env=env
        )
        == cli.EXIT_ERROR
    )
    payload = out.payload()
    assert payload["terminal"] == "FAILED:u1 severed-stream (receipt-incomplete)"
    assert_enveloped(payload)


def test_the_prompt_can_come_from_stdin() -> None:
    env, _, spawn, _ = environment(
        outcomes=[SpawnOutcome(exit_code=0, stdout=b"ok")], stdin_text="piped prompt"
    )
    cli.main(["run", "demo", "--unit-id", "u1", "--prompt-stdin"], env=env)
    assert spawn.calls[0]["stdin_payload"] == "piped prompt"


def test_there_is_no_prompt_text_flag_at_all() -> None:
    """Accepting prompt TEXT would put it on THIS process's argv."""
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "demo", "--unit-id", "u1", "--prompt", "hello"])


def test_a_prompt_source_is_mandatory_and_mutually_exclusive() -> None:
    parser = cli.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "demo", "--unit-id", "u1"])
    with pytest.raises(SystemExit):
        parser.parse_args(
            ["run", "demo", "--unit-id", "u1", "--prompt-stdin", "--prompt-file", "x"]
        )


# --------------------------------------------------------------------------------------------
# refusals -- every one still emits the full envelope
# --------------------------------------------------------------------------------------------


def test_an_unverified_rail_is_refused_without_the_opt_in() -> None:
    code, payload = run(
        ["run", "shaky", "--unit-id", "u1", "--prompt-file", PROMPT_FILE]
    )
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 policy-violation"
    assert "UNVERIFIED" in str(payload["error"])
    assert_enveloped(payload)


def test_the_unverified_opt_in_is_explicit_and_works() -> None:
    env, out, spawn, _ = environment(
        outcomes=[SpawnOutcome(exit_code=0, stdout=b"done")]
    )
    code = cli.main(
        [
            "run",
            "shaky",
            "--unit-id",
            "u1",
            "--prompt-file",
            PROMPT_FILE,
            "--allow-unverified",
        ],
        env=env,
    )
    assert code == cli.EXIT_OK
    assert len(spawn.calls) == 1


def test_a_missing_prompt_file_is_reported_as_env_missing() -> None:
    code, payload = run(["plan", "demo", "--unit-id", "u1", "--prompt-file", "/nope"])
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 env-missing"
    assert_enveloped(payload)


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_an_empty_prompt_is_refused(text: str) -> None:
    code, payload = run(
        ["plan", "demo", "--unit-id", "u1", "--prompt-stdin"], stdin_text=text
    )
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 policy-violation"


def test_a_missing_executable_at_plan_time_is_enveloped() -> None:
    env, out, _, fs = environment()
    del fs.files[EXE]
    assert (
        cli.main(
            ["plan", "demo", "--unit-id", "u1", "--prompt-file", PROMPT_FILE], env=env
        )
        == cli.EXIT_ERROR
    )
    assert out.payload()["terminal"] == "FAILED:u1 env-missing"


def test_an_illegal_dispatch_shape_is_enveloped() -> None:
    code, payload = run(
        [
            "plan",
            "demo",
            "--unit-id",
            "u1",
            "--prompt-file",
            PROMPT_FILE,
            "--timeout-s",
            "0",
        ]
    )
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 policy-violation"
    assert "nonpositive-timeout" in str(payload["error"])


def test_an_unknown_rail_is_enveloped_as_a_config_failure() -> None:
    code, payload = run(["resolve", "nope"])
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:agentrail policy-violation"
    assert "known rails:" in str(payload["error"])
    assert_enveloped(payload)


def test_a_missing_config_file_is_enveloped() -> None:
    code, payload = run(["--config", "/absent.toml", "rails"])
    assert code == cli.EXIT_ERROR
    assert "does not exist" in str(payload["error"])


def test_an_over_cap_argv_reaching_main_is_enveloped_as_win_arg_limit() -> None:
    toml = RAILS_TOML.replace(
        '[rail.demo]\nexe_globs = ["${HOME}/bin/*"]',
        '[rail.demo]\nexe_globs = ["${HOME}/bin/*"]\ncap = 40',
    )
    code, payload = run(
        [
            "run",
            "demo",
            "--unit-id",
            "u1",
            "--prompt-file",
            PROMPT_FILE,
            "--flag=" + "y" * 80,
        ],
        files={CONFIG: toml.encode("utf-8")},
    )
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 win-arg-limit"
    assert_enveloped(payload)


def test_a_prompt_colliding_with_a_caller_flag_is_enveloped_as_a_policy_violation() -> (
    None
):
    code, payload = run(
        [
            "run",
            "demo",
            "--unit-id",
            "u1",
            "--prompt-stdin",
            "--flag=collide",
        ],
        stdin_text="collide",
    )
    assert code == cli.EXIT_ERROR
    assert payload["terminal"] == "FAILED:u1 policy-violation"
    assert "PromptOnArgv" in str(payload["error"])


# --------------------------------------------------------------------------------------------
# deploy
# --------------------------------------------------------------------------------------------


def test_deploy_writes_the_shim_then_refuses_to_truncate_it() -> None:
    env, out, _, fs = environment()
    target = "/home/u/.local/bin/agentrail.cmd"

    assert cli.main(["deploy", "--target", target], env=env) == cli.EXIT_OK
    first = out.payload()
    assert first["status"] == "success"
    assert "action=write" in first["artifacts"]  # pyright: ignore[reportOperatorIssue]
    body = fs.files[target]

    assert cli.main(["deploy", "--target", target], env=env) == cli.EXIT_OK
    second = out.payload()
    assert second["status"] == "warning"
    assert fs.files[target] == body, "the existing shim must be byte-identical"
    assert_enveloped(second)


def test_deploy_overwrites_only_on_the_explicit_opt_in() -> None:
    env, out, _, fs = environment(files={"/t/agentrail.cmd": b"stale"})
    assert (
        cli.main(["deploy", "--target", "/t/agentrail.cmd", "--overwrite"], env=env)
        == cli.EXIT_OK
    )
    assert out.payload()["status"] == "success"
    assert fs.files["/t/agentrail.cmd"] != b"stale"


def test_the_shim_prefers_the_canonical_checkout_over_this_one() -> None:
    """A shim generated from a throwaway worktree must not be the ONLY root it knows."""
    env, _, _, fs = environment()
    roots = cli.candidate_tools_dirs(env)
    assert roots[0].endswith("agent-skills-toolchain\\tools") or roots[0].endswith(
        "agent-skills-toolchain/tools"
    )
    assert env.tools_dir in roots
    assert len(roots) == len(set(roots))

    cli.main(["deploy", "--target", "/t/agentrail.cmd"], env=env)
    body = fs.files["/t/agentrail.cmd"].decode("utf-8")
    assert body.count("if not defined AGENTRAIL_TOOLS if exist") == len(roots)


def test_the_candidate_roots_collapse_when_they_are_the_same_directory() -> None:
    env, _, _, _ = environment()
    same = str(Path(env.home) / "source" / "agent-skills-toolchain" / "tools")
    assert cli.candidate_tools_dirs(
        cli.Environment(
            ports=env.ports,
            home=env.home,
            tools_dir=same,
            config_path=env.config_path,
            out=env.out,
            stdin_text=env.stdin_text,
        )
    ) == (same,)


def test_deploy_defaults_to_the_users_local_bin() -> None:
    env, out, _, fs = environment()
    cli.main(["deploy"], env=env)
    assert any(SHIM_NAME in path for path in fs.files)
    assert ".local" in str(out.payload()["artifacts"])


# --------------------------------------------------------------------------------------------
# wiring
# --------------------------------------------------------------------------------------------


def test_main_falls_back_to_the_real_environment(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reads the SHIPPED rails.toml off disk. Filesystem only -- no spawn, no network."""
    assert cli.main(["rails"]) == cli.EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "success"
    assert any("codex" in item for item in payload["artifacts"])


def test_console_main_reads_sys_argv(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentrail", "rails"])
    assert cli.console_main() == cli.EXIT_OK
    assert json.loads(capsys.readouterr().out)["status"] == "success"


def test_the_default_environment_points_at_the_shipped_config() -> None:
    env = cli.default_environment()
    assert Path(env.config_path).name == "rails.toml"
    assert Path(env.config_path).is_file()
    assert Path(env.tools_dir).name == "tools"
    assert env.home


def test_the_default_stdin_reader_is_wired(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli.sys, "stdin", _FakeStdin("piped"))
    assert cli.default_environment().stdin_text() == "piped"


def test_the_default_printer_writes_to_stdout(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli.default_environment().out("hello")
    assert capsys.readouterr().out == "hello\n"


class _FakeStdin:
    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text
