"""Tests for the Goose ``custom_providers/`` file-set materializer (WU-7, D4 wave A).

The renderer owns only files carrying the ``managed-by`` marker: it writes one
``<endpoint-id>.json`` per endpoint the ``goose`` runtime takes, deletes stale
marked files, never touches an unmarked file and refuses a name collision with
one. ``HUGGINGFACE_TOKEN_INFERENCE`` is set to a fake value for every test and
must never reach a rendered file, an error message or stdout.
"""

from __future__ import annotations

import copy
import importlib
import json
import pathlib
import runpy
import subprocess
import sys
from collections.abc import Iterator, Mapping
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
SEED_PATH = AGENTS_ROOT / "models.json"
SCRIPT_PATH = SCRIPTS_ROOT / "merge_generated_goose_models.py"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
models = importlib.import_module("models_control_plane")
common = importlib.import_module("models_materialize_common")
goose = importlib.import_module("merge_generated_goose_models")

SEED: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
CREDENTIAL = "HUGGINGFACE_TOKEN_INFERENCE"
FAKE_VALUE = "FAKE_HF_VALUE_NOT_A_TOKEN"
MARKER = common.managed_marker(SEED)
GOOSE_ENDPOINTS = ("cursor-auth2api", "hf-router", "lmstudio", "ollama")
EXCLUDED_ROUTES = (
    "ROUTE:goose llamacpp excluded reason=enabled:false alternative=- "
    "wrappers=unprobed",
    "ROUTE:goose openrouter excluded reason=targets:excluded "
    "alternative=inference-hub wrappers=ok",
)
HAND_WRITTEN = (
    '{\n  "name": "goose-cursor-proxy",\n  "engine": "openai",\n'
    '  "base_url": "http://127.0.0.1:8317",\n  "models": []\n}\n'
)


@pytest.fixture(autouse=True)
def fake_credential(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv(CREDENTIAL, FAKE_VALUE)
    yield


class FakeRun:
    def __init__(self, returncode: int = 0) -> None:
        self.returncode = returncode
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(
        self, cmd: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, self.returncode, "", "")


def seed() -> dict[str, Any]:
    return copy.deepcopy(SEED)


def write_registry(tmp_path: pathlib.Path, config: Mapping[str, Any]) -> str:
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


def live_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    directory = tmp_path / "custom_providers"
    directory.mkdir(exist_ok=True)
    return directory


def run_main(
    tmp_path: pathlib.Path,
    *flags: str,
    registry: str | None = None,
    run: Any = None,
) -> int:
    argv = [
        "--registry",
        registry or str(SEED_PATH),
        "--live",
        str(tmp_path / "custom_providers"),
        *flags,
    ]
    return goose.main(argv, run=run)


def success_line(out: str) -> str:
    lines = [line for line in out.splitlines() if not line.startswith("ROUTE:")]
    assert len(lines) == 1, out
    return lines[0]


def backups_in(directory: pathlib.Path) -> list[pathlib.Path]:
    return sorted(directory.glob("*.bak-*"))


def assert_no_secret(*texts: str) -> None:
    for text in texts:
        assert FAKE_VALUE not in text
        assert "api_key" not in text.replace("api_key_env", "")


# --- rendering ---------------------------------------------------------------------


def test_render_provider_fields_for_an_authenticated_endpoint() -> None:
    selected = models.select_target_models(SEED, "goose")
    payload = goose.render_provider(
        "hf-router", SEED["endpoints"]["hf-router"], selected, MARKER
    )
    assert payload == {
        "name": "hf-router",
        "engine": "openai",
        "display_name": "Hugging Face Inference Providers router",
        "description": f"Hugging Face Inference Providers router - {MARKER}",
        "api_key_env": "HUGGINGFACE_TOKEN_INFERENCE",
        "base_url": "https://router.huggingface.co",
        "base_path": "v1/chat/completions",
        "models": [{"name": "zai-org/GLM-5.3:zai-org", "context_limit": 131072}],
        "supports_streaming": True,
        "requires_auth": True,
    }
    assert list(payload) == [
        "name",
        "engine",
        "display_name",
        "description",
        "api_key_env",
        "base_url",
        "base_path",
        "models",
        "supports_streaming",
        "requires_auth",
    ]


def test_render_provider_omits_api_key_env_without_auth() -> None:
    selected = models.select_target_models(SEED, "goose")
    payload = goose.render_provider(
        "ollama", SEED["endpoints"]["ollama"], selected, MARKER
    )
    assert "api_key_env" not in payload
    assert payload["requires_auth"] is False
    assert payload["base_url"] == "http://127.0.0.1:11434"
    assert [row["name"] for row in payload["models"]] == [
        "qwen2.5:7b",
        "qwen3:4b-instruct-2507-q4_K_M",
        "qwen3:8b",
    ]
    assert all(row["context_limit"] == 8192 for row in payload["models"])


def test_render_files_one_per_selected_endpoint() -> None:
    rendered, model_count = goose.render_files(SEED)
    assert sorted(rendered) == [f"{name}.json" for name in GOOSE_ENDPOINTS]
    assert model_count == 5
    for name, text in rendered.items():
        payload = json.loads(text)
        assert text.endswith("}\n")
        assert payload["name"] == name[: -len(".json")]
        assert payload["engine"] == "openai"
        assert MARKER in payload["description"]
        assert common.MANAGED_MARKER_RE.search(text) is not None
        assert_no_secret(text)
    assert json.loads(rendered["lmstudio.json"])["models"] == []
    assert json.loads(rendered["cursor-auth2api.json"])["models"] == [
        {"name": "cursor-grok-4.6", "context_limit": 131072}
    ]


def test_scan_live_separates_marked_unmarked_and_non_files(
    tmp_path: pathlib.Path,
) -> None:
    directory = live_dir(tmp_path)
    assert goose.scan_live(tmp_path / "absent") == ({}, set())
    (directory / "goose-cursor-proxy.json").write_text(HAND_WRITTEN, encoding="utf-8")
    (directory / "old.json").write_text(
        json.dumps({"description": f"x - {MARKER}"}), encoding="utf-8"
    )
    (directory / "notes.txt").write_text(MARKER, encoding="utf-8")
    (directory / "folder.json").mkdir()
    (directory / "binary.json").write_bytes(b"\xff\xfe{}")
    existing, marked = goose.scan_live(directory)
    assert sorted(existing) == ["binary.json", "goose-cursor-proxy.json", "old.json"]
    assert marked == {"old.json"}


def test_plan_refuses_to_overwrite_an_unmarked_collision(
    tmp_path: pathlib.Path,
) -> None:
    directory = live_dir(tmp_path)
    (directory / "hf-router.json").write_text(HAND_WRITTEN, encoding="utf-8")
    with pytest.raises(
        goose.GooseMergeError, match="without the managed marker"
    ) as info:
        goose.plan(SEED, directory)
    assert str(directory / "hf-router.json") in str(info.value)


def test_plan_counts_writes_deletes_and_preserved(tmp_path: pathlib.Path) -> None:
    directory = live_dir(tmp_path)
    rendered, _ = goose.render_files(SEED)
    (directory / "ollama.json").write_text(rendered["ollama.json"], encoding="utf-8")
    (directory / "hf-router.json").write_text(
        rendered["hf-router.json"].replace(
            MARKER, "managed-by: .agents/models.json 0123456789abcdef"
        ),
        encoding="utf-8",
    )
    (directory / "stale.json").write_text(
        json.dumps({"description": MARKER}), encoding="utf-8"
    )
    (directory / "goose-cursor-proxy.json").write_text(HAND_WRITTEN, encoding="utf-8")
    plan = goose.plan(SEED, directory)
    assert plan.writes == ["cursor-auth2api.json", "hf-router.json", "lmstudio.json"]
    assert plan.deletes == ["stale.json"]
    assert plan.preserved == ["goose-cursor-proxy.json"]
    assert plan.drift == plan.writes + plan.deletes
    assert plan.model_count == 5


# --- dry run, routing report, check ----------------------------------------------------


def test_dry_run_reports_counts_and_every_routing_decision(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path) == 0
    out = capsys.readouterr().out
    routes = [line for line in out.splitlines() if line.startswith("ROUTE:goose ")]
    assert len(routes) == len(SEED["endpoints"])
    for line in EXCLUDED_ROUTES:
        assert line in routes
    assert success_line(out) == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=4 deleted=0 "
        "preserved=0 write=false"
    )
    assert not (tmp_path / "custom_providers").exists()
    assert_no_secret(out)


def test_quiet_hides_the_routing_report(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--quiet") == 0
    out = capsys.readouterr().out
    assert "ROUTE:" not in out
    assert out.startswith("SUCCESS:goose-models-merge ")


def test_check_reports_drift_then_passes_after_write(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--check", "--quiet") == 1
    assert capsys.readouterr().out == (
        "FAILED:goose-models-merge check drift=cursor-auth2api.json,hf-router.json,"
        "lmstudio.json,ollama.json\n"
    )
    assert run_main(tmp_path, "--write", "--quiet") == 0
    capsys.readouterr()
    assert run_main(tmp_path, "--check", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=0 deleted=0 "
        "preserved=0 write=false\n"
    )
    directory = live_dir(tmp_path)
    (directory / "stale.json").write_text(json.dumps({"d": MARKER}), encoding="utf-8")
    assert run_main(tmp_path, "--check", "--quiet") == 1
    assert (
        capsys.readouterr().out == "FAILED:goose-models-merge check drift=stale.json\n"
    )


# --- write ---------------------------------------------------------------------------


def test_write_creates_the_file_set_and_is_idempotent(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=4 deleted=0 "
        "preserved=0 write=true\n"
    )
    directory = tmp_path / "custom_providers"
    assert sorted(p.name for p in directory.iterdir()) == [
        f"{name}.json" for name in GOOSE_ENDPOINTS
    ]
    first = {p.name: p.read_bytes() for p in directory.iterdir()}
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=0 deleted=0 "
        "preserved=0 write=true\n"
    )
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == first
    assert backups_in(directory) == []
    for text in first.values():
        assert_no_secret(text.decode("utf-8"))


def test_write_touches_only_marked_files(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = live_dir(tmp_path)
    hand = directory / "goose-cursor-proxy.json"
    hand.write_bytes(HAND_WRITTEN.encode("utf-8"))
    stale = directory / "stale.json"
    stale.write_text(json.dumps({"description": f"old - {MARKER}"}), encoding="utf-8")
    outdated = directory / "ollama.json"
    outdated.write_text(
        json.dumps({"description": MARKER, "models": []}), encoding="utf-8"
    )
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=4 deleted=1 "
        "preserved=1 write=true\n"
    )
    assert hand.read_bytes() == HAND_WRITTEN.encode("utf-8")
    assert not stale.exists()
    assert json.loads(outdated.read_text(encoding="utf-8"))["name"] == "ollama"
    backups = backups_in(directory)
    assert [p.name.split(".bak-")[0] for p in backups] == ["ollama.json", "stale.json"]
    assert backups[1].read_text(encoding="utf-8") == json.dumps(
        {"description": f"old - {MARKER}"}
    )
    assert sorted(p.name for p in directory.iterdir() if ".bak-" not in p.name) == [
        "cursor-auth2api.json",
        "goose-cursor-proxy.json",
        "hf-router.json",
        "lmstudio.json",
        "ollama.json",
    ]


def test_write_no_backup_leaves_no_bak_files(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = live_dir(tmp_path)
    (directory / "stale.json").write_text(json.dumps({"d": MARKER}), encoding="utf-8")
    (directory / "hf-router.json").write_text(
        json.dumps({"d": MARKER}), encoding="utf-8"
    )
    assert run_main(tmp_path, "--write", "--no-backup", "--quiet") == 0
    assert "written=4 deleted=1 preserved=0 write=true" in capsys.readouterr().out
    assert backups_in(directory) == []
    assert not (directory / "stale.json").exists()
    assert (
        json.loads((directory / "hf-router.json").read_text(encoding="utf-8"))["engine"]
        == "openai"
    )


def test_write_reflects_registry_changes_by_deleting_managed_files(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--write", "--quiet") == 0
    config = seed()
    config["endpoints"]["lmstudio"]["targets"]["goose"] = "excluded"
    registry = write_registry(tmp_path, config)
    assert run_main(tmp_path, "--write", "--quiet", registry=registry) == 0
    out = capsys.readouterr().out.splitlines()[-1]
    assert out == (
        "SUCCESS:goose-models-merge endpoints=3 models=5 written=3 deleted=1 "
        "preserved=0 write=true"
    )
    directory = tmp_path / "custom_providers"
    assert not (directory / "lmstudio.json").exists()
    assert len(backups_in(directory)) == 4


# --- smoke + rollback ------------------------------------------------------------------


def test_smoke_pass_keeps_the_write(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = FakeRun(returncode=0)
    assert run_main(tmp_path, "--write", "--smoke", "--quiet", run=run) == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=4 deleted=0 "
        "preserved=0 write=true smoke=true\n"
    )
    assert run.calls[0][0] == ["goose", "info"]
    assert run.calls[0][1]["env"] is None
    assert (tmp_path / "custom_providers" / "hf-router.json").exists()


def test_smoke_failure_restores_every_path_byte_for_byte(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = live_dir(tmp_path)
    hand = directory / "goose-cursor-proxy.json"
    hand.write_bytes(HAND_WRITTEN.encode("utf-8"))
    stale = directory / "stale.json"
    stale_bytes = json.dumps({"description": f"old - {MARKER}"}).encode("utf-8")
    stale.write_bytes(stale_bytes)
    outdated = directory / "ollama.json"
    outdated_bytes = b'{"description": "' + MARKER.encode("utf-8") + b'"}\r\n'
    outdated.write_bytes(outdated_bytes)
    run = FakeRun(returncode=1)
    assert run_main(tmp_path, "--write", "--smoke", "--quiet", run=run) == 2
    out = capsys.readouterr().out
    assert out.startswith(
        "FAILED:goose-models-merge smoke 'goose info' failed; restored 5 path(s)"
    )
    assert_no_secret(out)
    assert hand.read_bytes() == HAND_WRITTEN.encode("utf-8")
    assert stale.read_bytes() == stale_bytes
    assert outdated.read_bytes() == outdated_bytes
    assert sorted(p.name for p in directory.iterdir() if ".bak-" not in p.name) == [
        "goose-cursor-proxy.json",
        "ollama.json",
        "stale.json",
    ]


# --- failures ------------------------------------------------------------------------------


def test_invalid_registry_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = seed()
    config["endpoints"]["hf-router"]["targets"]["goose"] = "sometimes"
    registry = write_registry(tmp_path, config)
    assert run_main(tmp_path, "--write", registry=registry) == 2
    out = capsys.readouterr().out
    assert out.startswith("FAILED:goose-models-merge hf-router: targets.goose")
    assert not (tmp_path / "custom_providers").exists()


def test_unmarked_collision_fails_before_anything_is_written(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = live_dir(tmp_path)
    (directory / "ollama.json").write_text(HAND_WRITTEN, encoding="utf-8")
    assert run_main(tmp_path, "--write") == 2
    out = capsys.readouterr().out
    assert out.startswith("FAILED:goose-models-merge ")
    assert "ollama.json exists without the managed marker" in out
    assert "ROUTE:" not in out
    assert sorted(p.name for p in directory.iterdir()) == ["ollama.json"]


def test_a_credential_value_in_the_render_fails_by_name_only(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(CREDENTIAL, "router.huggingface.co")
    assert run_main(tmp_path, "--write") == 2
    out = capsys.readouterr().out
    assert out == (
        "FAILED:goose-models-merge rendered text contains the value of "
        "HUGGINGFACE_TOKEN_INFERENCE (len=21); credentials are referenced by name "
        "only (L6)\n"
    )
    assert not (tmp_path / "custom_providers").exists()


# --- entry points ------------------------------------------------------------------------


def test_module_entrypoint(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT_PATH),
            "--registry",
            str(SEED_PATH),
            "--live",
            str(tmp_path / "custom_providers"),
            "--quiet",
        ],
    )
    with pytest.raises(SystemExit) as info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
    assert info.value.code == 0
    assert capsys.readouterr().out == (
        "SUCCESS:goose-models-merge endpoints=4 models=5 written=4 deleted=0 "
        "preserved=0 write=false\n"
    )


def test_default_live_is_the_windows_custom_providers_directory() -> None:
    parser = common.build_parser(goose.NAME, default_live=goose.DEFAULT_LIVE_DIR)
    assert (
        parser.parse_args([]).live == r"%APPDATA%\Block\goose\config\custom_providers"
    )
    assert goose.SMOKE_COMMAND == ("goose", "info")
