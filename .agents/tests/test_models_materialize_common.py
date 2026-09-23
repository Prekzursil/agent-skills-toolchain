"""Tests for the shared renderer primitives in ``models_materialize_common``.

Every credential value used here is assembled at runtime and never has a real
token shape; the one environment value the suite sets
(``HUGGINGFACE_TOKEN_INFERENCE=FAKE_HF_VALUE_NOT_A_TOKEN``) must never reach a
rendered text, an error message or stdout.
"""

from __future__ import annotations

import argparse
import copy
import importlib
import json
import pathlib
import re
import subprocess
import sys
from collections.abc import Mapping
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
SEED_PATH = AGENTS_ROOT / "models.json"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
models = importlib.import_module("models_control_plane")
common = importlib.import_module("models_materialize_common")

SEED: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
CREDENTIAL = "HUGGINGFACE_TOKEN_INFERENCE"
FAKE_VALUE = "FAKE_HF_VALUE_NOT_A_TOKEN"
FAKE_HF = "hf_" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_SK = "sk-" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_GHP = "ghp_" + "FAKE_VALUE_NOT_A_TOKEN"
FAKE_AWS = "AKIA" + "NOTAREALKEYFAKE0"
FAKE_SLACK = "xoxb-" + "FAKE-NOT-A-TOKEN"
FAKE_PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
BACKUP_RE = re.compile(r"\.bak-\d{8}-\d{6}(?:-\d+)?$")


def seed() -> dict[str, Any]:
    return copy.deepcopy(SEED)


def namespace(**values: object) -> argparse.Namespace:
    return argparse.Namespace(**values)


class FakeRun:
    """A ``subprocess.run`` stand-in recording its call and returning a code."""

    def __init__(self, returncode: int = 0, error: OSError | None = None) -> None:
        self.returncode = returncode
        self.error = error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(
        self, cmd: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, kwargs))
        if self.error is not None:
            raise self.error
        return subprocess.CompletedProcess(cmd, self.returncode, "", "")


# --- marker, dataclass, parser ---------------------------------------------------


def test_managed_marker_carries_the_registry_hash() -> None:
    marker = common.managed_marker(SEED)
    digest = models.registry_hash(SEED)
    assert marker == f"managed-by: .agents/models.json {digest}"
    match = common.MANAGED_MARKER_RE.search(f"# {marker}\n[table]")
    assert match is not None and match.group("hash") == digest
    assert (
        common.MANAGED_MARKER_RE.search("managed-by: .agents/models.json ABC") is None
    )
    assert common.managed_marker(seed()) == marker


def test_render_result_defaults() -> None:
    result = common.RenderResult(runtime="grok", managed={"a": 1}, routing=[])
    assert (result.written, result.backup, result.drift) == (False, None, [])
    result.drift.append("settings.toml")
    assert common.RenderResult("goose", {}, []).drift == []


def test_build_parser_defaults_and_shared_flags() -> None:
    parser = common.build_parser("demo-merge", pathlib.Path(r"C:\live\config.toml"))
    args = parser.parse_args([])
    assert parser.prog == "demo-merge"
    assert args.registry == str(models.DEFAULT_REGISTRY_PATH)
    assert args.live == r"C:\live\config.toml"
    assert (args.write, args.check, args.no_backup, args.quiet) == (
        False,
        False,
        False,
        False,
    )
    args = parser.parse_args(
        [
            "--registry",
            "r.json",
            "--live",
            "l.toml",
            "--write",
            "--no-backup",
            "--quiet",
        ]
    )
    assert (args.registry, args.live) == ("r.json", "l.toml")
    assert (args.write, args.check, args.no_backup, args.quiet) == (
        True,
        False,
        True,
        True,
    )
    assert parser.parse_args(["--check"]).check is True
    custom = common.build_parser("x", "live", description="custom text")
    assert custom.description == "custom text"
    assert "dry run" in str(parser.description)


def test_build_parser_refuses_write_with_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = common.build_parser("demo-merge", "live")
    with pytest.raises(SystemExit) as info:
        parser.parse_args(["--write", "--check"])
    assert info.value.code == 2
    assert "not allowed with argument" in capsys.readouterr().err


def test_live_path_expands_placeholders(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MM_TEST_LIVE_DIR", str(tmp_path))
    args = namespace(live="${MM_TEST_LIVE_DIR}/custom_providers")
    assert common.live_path(args) == tmp_path / "custom_providers"
    assert common.live_path(namespace(live=str(tmp_path))) == tmp_path


def test_read_text_distinguishes_files_from_everything_else(
    tmp_path: pathlib.Path,
) -> None:
    target = tmp_path / "live.toml"
    assert common.read_text(target) is None
    assert common.read_text(tmp_path) is None
    target.write_text("a = 1\n", encoding="utf-8")
    assert common.read_text(target) == "a = 1\n"


# --- load_inputs -------------------------------------------------------------------


def test_load_inputs_returns_the_registry_and_the_live_text(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    live = tmp_path / "settings.toml"
    live.write_text('[models]\ndefault = "x"\n', encoding="utf-8")
    config, text = common.load_inputs(
        namespace(registry=str(SEED_PATH), live=str(live))
    )
    assert config == SEED
    assert text == '[models]\ndefault = "x"\n'
    assert capsys.readouterr() == ("", "")
    _, missing = common.load_inputs(
        namespace(registry=str(SEED_PATH), live=str(tmp_path / "absent"))
    )
    assert missing is None
    _, directory = common.load_inputs(
        namespace(registry=str(SEED_PATH), live=str(tmp_path))
    )
    assert directory is None


def test_load_inputs_reports_warnings_on_stderr(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = seed()
    config["models"]["qwen3-8b"]["resource"]["ramBytes"] = 8 * 1024**3
    registry = tmp_path / "models.json"
    registry.write_text(json.dumps(config), encoding="utf-8")
    loaded, _ = common.load_inputs(namespace(registry=str(registry), live="x"))
    assert loaded == config
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("WARNING:models-registry local RAM")


def test_load_inputs_raises_registry_errors_for_every_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(
        models.ModelsRegistryError, match="cannot read registry"
    ) as info:
        common.load_inputs(namespace(registry=str(missing), live="x"))
    assert str(missing) in str(info.value)
    config = seed()
    config["extra"] = 1
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(models.ModelsRegistryError, match="unknown registry key"):
        common.load_inputs(namespace(registry=str(invalid), live="x"))
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    with pytest.raises(models.ModelsRegistryError, match="invalid JSON"):
        common.load_inputs(namespace(registry=str(broken), live="x"))

    def unreadable(path: pathlib.Path) -> str | None:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(common, "read_text", unreadable)
    live = tmp_path / "live.toml"
    with pytest.raises(models.ModelsRegistryError, match="cannot read live config"):
        common.load_inputs(namespace(registry=str(SEED_PATH), live=str(live)))


# --- backups, writes, removals ----------------------------------------------------


def backups_of(path: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path.parent.glob(f"{path.name}.bak-*"))


def test_write_with_backup_creates_then_backs_up(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "nested" / "settings.toml"
    assert common.write_with_backup(target, "first\n") is None
    assert target.read_text(encoding="utf-8") == "first\n"
    assert backups_of(target) == []
    backup = common.write_with_backup(target, "second\n")
    assert backup is not None and backup.exists()
    assert BACKUP_RE.search(backup.name) is not None
    assert backup.name.startswith("settings.toml.bak-")
    assert backup.read_text(encoding="utf-8") == "first\n"
    assert target.read_text(encoding="utf-8") == "second\n"
    assert common.write_with_backup(target, "third\n", backup=False) is None
    assert target.read_text(encoding="utf-8") == "third\n"
    assert backups_of(target) == [backup]
    assert common.write_with_backup(str(target), "third\n") is not None
    assert not list(target.parent.glob(".settings.toml.*.tmp"))


def test_backup_names_never_collide_within_one_second(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(common, "_timestamp", lambda: "20260902-120000")
    target = tmp_path / "config.json"
    target.write_text("v0", encoding="utf-8")
    first = common.backup_file(target)
    target.write_text("v1", encoding="utf-8")
    second = common.backup_file(target)
    target.write_text("v2", encoding="utf-8")
    third = common.backup_file(target)
    assert first is not None and second is not None and third is not None
    assert first.name == "config.json.bak-20260902-120000"
    assert second.name == "config.json.bak-20260902-120000-1"
    assert third.name == "config.json.bak-20260902-120000-2"
    assert [p.read_text(encoding="utf-8") for p in (first, second, third)] == [
        "v0",
        "v1",
        "v2",
    ]
    assert common.backup_file(tmp_path / "absent.json") is None


def test_remove_with_backup(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "old.json"
    assert common.remove_with_backup(target) is None
    target.write_text("{}", encoding="utf-8")
    backup = common.remove_with_backup(str(target))
    assert backup is not None and backup.read_text(encoding="utf-8") == "{}"
    assert not target.exists()
    target.write_text("{}", encoding="utf-8")
    assert common.remove_with_backup(target, backup=False) is None
    assert not target.exists()
    assert backups_of(target) == [backup]


# --- reporting ------------------------------------------------------------------------


def test_print_routing_report_one_line_per_endpoint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows = models.routing_report(SEED, "goose")
    common.print_routing_report(rows)
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(SEED["endpoints"])
    assert all(line.startswith("ROUTE:goose ") for line in lines)
    assert (
        "ROUTE:goose openrouter excluded reason=targets:excluded "
        "alternative=inference-hub wrappers=ok"
    ) in lines
    assert (
        "ROUTE:goose hf-router included reason=targets:native alternative=- wrappers=ok"
    ) in lines
    assert (
        "ROUTE:goose llamacpp excluded reason=enabled:false alternative=- "
        "wrappers=unprobed"
    ) in lines
    common.print_routing_report([])
    assert capsys.readouterr().out == ""


def test_print_success_and_fail_lines(capsys: pytest.CaptureFixture[str]) -> None:
    assert common.print_success("demo", endpoints=4, write=True, check=False) == 0
    assert (
        capsys.readouterr().out == "SUCCESS:demo endpoints=4 write=true check=false\n"
    )
    assert common.print_success("demo") == 0
    assert capsys.readouterr().out == "SUCCESS:demo\n"
    assert common.print_success("demo", mode="dry-run", drift=0) == 0
    assert capsys.readouterr().out == "SUCCESS:demo mode=dry-run drift=0\n"
    assert common.fail("demo", "first line\n  second\tline  ") == 2
    captured = capsys.readouterr()
    assert captured.out == "FAILED:demo first line second line\n"
    assert captured.err == ""


# --- smoke + rollback -------------------------------------------------------------


def prepare_written(
    tmp_path: pathlib.Path,
) -> tuple[list[pathlib.Path], dict[pathlib.Path, pathlib.Path | None], bytes]:
    modified = tmp_path / "modified.toml"
    original = b'[models]\r\ndefault = "x"\r\n\xc3\xa9\n'
    modified.write_bytes(original)
    backup = common.write_with_backup(modified, "rewritten\n")
    created = tmp_path / "created.json"
    assert common.write_with_backup(created, "{}\n") is None
    deleted = tmp_path / "deleted.json"
    deleted.write_bytes(b"gone\n")
    deleted_backup = common.remove_with_backup(deleted)
    written = [modified, created, deleted]
    backups = {modified: backup, created: None, deleted: deleted_backup}
    return written, backups, original


def test_rollback_restores_modified_deletes_created_and_revives_deleted(
    tmp_path: pathlib.Path,
) -> None:
    written, backups, original = prepare_written(tmp_path)
    restored = common.rollback(written, backups)
    assert restored == written
    assert written[0].read_bytes() == original
    assert not written[1].exists()
    assert written[2].read_bytes() == b"gone\n"
    assert common.rollback(written, backups) == written
    assert common.rollback([tmp_path / "never-written"], {}) == [
        tmp_path / "never-written"
    ]


def test_rollback_leaves_no_temporary_file_when_the_replace_fails(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written, backups, _ = prepare_written(tmp_path)

    def broken_replace(src: str, dst: str) -> None:
        raise OSError(28, "No space left on device", str(dst))

    monkeypatch.setattr(common.os, "replace", broken_replace)
    with pytest.raises(OSError, match="No space left"):
        common.rollback(written[:1], backups)
    assert written[0].read_text(encoding="utf-8") == "rewritten\n"
    assert list(tmp_path.glob(".modified.toml.*.tmp")) == []


def test_smoke_and_rollback_keeps_files_when_the_smoke_passes(
    tmp_path: pathlib.Path,
) -> None:
    written, backups, _ = prepare_written(tmp_path)
    run = FakeRun(returncode=0)
    assert common.smoke_and_rollback(("goose", "info"), written, backups, run=run)
    assert written[0].read_text(encoding="utf-8") == "rewritten\n"
    assert written[1].exists()
    assert not written[2].exists()
    cmd, kwargs = run.calls[0]
    assert cmd == ["goose", "info"]
    assert kwargs == {
        "capture_output": True,
        "text": True,
        "check": False,
        "env": None,
    }


def test_smoke_and_rollback_restores_byte_for_byte_on_failure(
    tmp_path: pathlib.Path,
) -> None:
    written, backups, original = prepare_written(tmp_path)
    run = FakeRun(returncode=1)
    env = {"GROK_HOME": str(tmp_path)}
    assert (
        common.smoke_and_rollback(
            ["grok", "inspect"], written, backups, run=run, env=env
        )
        is False
    )
    assert written[0].read_bytes() == original
    assert not written[1].exists()
    assert written[2].read_bytes() == b"gone\n"
    assert run.calls[0][1]["env"] == {"GROK_HOME": str(tmp_path)}
    assert run.calls[0][1]["env"] is not env


def test_smoke_and_rollback_treats_a_missing_binary_as_failure(
    tmp_path: pathlib.Path,
) -> None:
    written, backups, original = prepare_written(tmp_path)
    run = FakeRun(error=FileNotFoundError(2, "No such file", "goose"))
    assert common.smoke_and_rollback(["goose"], written, backups, run=run) is False
    assert written[0].read_bytes() == original
    assert not written[1].exists()


def test_smoke_and_rollback_defaults_to_subprocess_run(tmp_path: pathlib.Path) -> None:
    written, backups, original = prepare_written(tmp_path)
    ok = [sys.executable, "-c", "raise SystemExit(0)"]
    assert common.smoke_and_rollback(ok, written, backups) is True
    assert written[0].read_text(encoding="utf-8") == "rewritten\n"
    bad = [sys.executable, "-c", "print('never shown'); raise SystemExit(3)"]
    assert common.smoke_and_rollback(bad, written, backups) is False
    assert written[0].read_bytes() == original


# --- secrets ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("bash", "${HUGGINGFACE_TOKEN_INFERENCE}"),
        ("goose", "HUGGINGFACE_TOKEN_INFERENCE"),
        ("grok", '["HUGGINGFACE_TOKEN_INFERENCE"]'),
        ("cursor", "${env:HUGGINGFACE_TOKEN_INFERENCE}"),
        ("opencode", "{env:HUGGINGFACE_TOKEN_INFERENCE}"),
    ],
)
def test_env_reference_styles(style: str, expected: str) -> None:
    assert common.env_reference(CREDENTIAL, style) == expected
    assert set(common.ENV_REFERENCE_STYLES) == {
        "bash",
        "goose",
        "grok",
        "cursor",
        "opencode",
    }


def test_env_reference_rejects_bad_names_and_styles() -> None:
    with pytest.raises(ValueError, match="unknown env reference style 'toml'"):
        common.env_reference(CREDENTIAL, "toml")
    with pytest.raises(ValueError, match="is not an environment variable name"):
        common.env_reference("lower_case", "bash")
    with pytest.raises(ValueError, match="is not an environment variable name"):
        common.env_reference(FAKE_VALUE.lower(), "goose")


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("base_url = 'https://router.huggingface.co/v1'", None),
        ('env_key = ["HF_TOKEN", "SK_LIVE_KEY"] ${HF_TOKEN} {env:GHP_X}', None),
        ("api_key_env: HUGGINGFACE_TOKEN_INFERENCE", None),
        (f"token={FAKE_HF}", "token-prefix"),
        (f'api_key = "{FAKE_SK}"', "token-prefix"),
        (f"Authorization: Bearer {FAKE_GHP}", "token-prefix"),
        (f"aws_access_key_id = {FAKE_AWS}", "aws-access-key"),
        (f"slack: {FAKE_SLACK}", "slack-token"),
        (FAKE_PEM + "\nabc\n", "pem-private-key"),
    ],
)
def test_literal_secret_kind(text: str, kind: str | None) -> None:
    assert common.literal_secret_kind(text) == kind


def test_assert_no_secret_values_refuses_set_credential_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CREDENTIAL, FAKE_VALUE)
    names = models.credential_names(SEED)
    environ: Mapping[str, str] = dict(**{CREDENTIAL: FAKE_VALUE})
    clean = f"api_key_env = {CREDENTIAL}\nbase_url = 'https://x/v1'\n"
    common.assert_no_secret_values(clean, environ, names)
    common.assert_no_secret_values(clean, environ, [CREDENTIAL, CREDENTIAL])
    leaked = f'api_key = "{FAKE_VALUE}"\n'
    with pytest.raises(common.SecretValueError) as info:
        common.assert_no_secret_values(leaked, environ, names)
    message = str(info.value)
    assert CREDENTIAL in message and f"len={len(FAKE_VALUE)}" in message
    assert FAKE_VALUE not in message
    common.assert_no_secret_values(leaked, {}, names)
    common.assert_no_secret_values(leaked, environ, ["OPENROUTER_API_KEY_CLI_GRUNT"])
    short = {CREDENTIAL: "abc1234"}
    common.assert_no_secret_values("abc1234 appears", short, names)
    common.assert_no_secret_values("anything", {CREDENTIAL: ""}, names)


def test_assert_no_secret_values_refuses_literal_shapes() -> None:
    with pytest.raises(common.SecretValueError, match="token-prefix"):
        common.assert_no_secret_values(f"key: {FAKE_SK}", {}, [])
    with pytest.raises(common.SecretValueError, match="pem-private-key"):
        common.assert_no_secret_values(FAKE_PEM, {}, [])
    common.assert_no_secret_values('env_key = ["HF_TOKEN"]', {}, [])


def test_strip_v1() -> None:
    assert common.strip_v1("https://router.huggingface.co/v1") == (
        "https://router.huggingface.co"
    )
    assert common.strip_v1("http://127.0.0.1:11434") == "http://127.0.0.1:11434"
    assert common.strip_v1("http://127.0.0.1:8317/v1") == "http://127.0.0.1:8317"
