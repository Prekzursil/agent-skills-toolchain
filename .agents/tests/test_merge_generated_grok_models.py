"""Tests for the Grok Build ``config.toml`` ``[model."<id>"]`` materializer (WU-7, D4 wave A).

The renderer owns only ``[model."<id>"]`` blocks introduced by the ``managed-by``
marker: it replaces them in place, appends the missing ones, removes the ones whose
id left the registry, and copies every other byte of the live file unchanged. An
unmanaged live block wins over the registry for the same id, ``api_key =`` is never
rendered, and ``[endpoints] models_base_url`` appears only while the Cursor bridge
carries a ``probed`` completions receipt. ``HUGGINGFACE_TOKEN_INFERENCE`` is set to a
fake value for every test and must never reach the merged text, an error message
or stdout.
"""

from __future__ import annotations

import copy
import importlib
import json
import pathlib
import runpy
import subprocess
import sys
import tomllib
from collections.abc import Iterator, Mapping
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
SEED_PATH = AGENTS_ROOT / "models.json"
SCRIPT_PATH = SCRIPTS_ROOT / "merge_generated_grok_models.py"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
models = importlib.import_module("models_control_plane")
common = importlib.import_module("models_materialize_common")
grok = importlib.import_module("merge_generated_grok_models")

SEED: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
CREDENTIAL = "HUGGINGFACE_TOKEN_INFERENCE"
FAKE_VALUE = "FAKE_HF_VALUE_NOT_A_TOKEN"
MARKER = common.managed_marker(SEED)
STALE_MARKER = "managed-by: .agents/models.json 0123456789abcdef"
PROBED = {"state": "probed", "at": "2026-09-02T00:00:00Z", "version": "probe"}
BRIDGE_URL = "http://127.0.0.1:8317/v1"
GROK_MODELS = (
    "cursor-grok-4.6",
    "glm-5.2-free",
    "glm-5.3",
    "qwen2.5-7b",
    "qwen3-4b-instruct",
    "qwen3-8b",
)
EXCLUDED_ROUTE = (
    "ROUTE:grok llamacpp excluded reason=enabled:false alternative=- wrappers=unprobed"
)
INCLUDED_ROUTE = (
    "ROUTE:grok hf-router included reason=targets:native alternative=- wrappers=ok"
)
LIVE_ONLY_BLOCK = (
    '[model."cursor-grok-4.6"]\n'
    'model = "cursor-grok-4.6"\n'
    f'base_url = "{BRIDGE_URL}"\n'
    'env_key = "CURSOR_AUTH2API_KEY"\n'
    'api_backend = "chat_completions"\n'
)
HAND_WRITTEN_BLOCK = (
    '  [model."hand-written"]   # indented header with a trailing comment\n'
    'model = "local-llm"\n'
    'base_url = "http://127.0.0.1:9999/v1"\n'
    "\n"
    '[model."hand-written".extra_headers]\n'
    'X-Trace = "on"\n'
)
LIVE = (
    "# Grok Build user config\n"
    "[models]\n"
    'default = "cursor-grok-4.6"\n'
    "\n"
    "[paths]\n"
    "extra_skill_dirs = ['C:\\Users\\Prekzursil\\.agents\\skills']\n"
    "\n"
    f"{LIVE_ONLY_BLOCK}"
    "\n"
    f"{HAND_WRITTEN_BLOCK}"
    "\n"
    "[[plugins]]\n"
    'name = "first"\n'
    "\n"
    '[mcp_servers."agent-mail"]\n'
    'url = "http://127.0.0.1:8812/mcp"\n'
    "\n"
)
UNMANAGED_ENDPOINTS = '[endpoints]\nmodels_base_url = "https://api.x.ai/v1"\n'


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


def probed_seed() -> dict[str, Any]:
    config = seed()
    config["endpoints"]["cursor-auth2api"]["wire"]["completions"] = dict(PROBED)
    return config


def write_registry(tmp_path: pathlib.Path, config: Mapping[str, Any]) -> str:
    path = tmp_path / "models.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return str(path)


def live_file(tmp_path: pathlib.Path) -> pathlib.Path:
    directory = tmp_path / "grok"
    directory.mkdir(exist_ok=True)
    return directory / "config.toml"


def managed_block(model_id: str, marker: str = MARKER) -> str:
    return (
        f"# {marker}\n"
        f'[model."{model_id}"]\n'
        'model = "old"\n'
        'base_url = "http://127.0.0.1:9/v1"\n'
    )


def managed_endpoints(marker: str = MARKER) -> str:
    return f'# {marker}\n[endpoints]\nmodels_base_url = "{BRIDGE_URL}"\n'


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
        str(tmp_path / "grok" / "config.toml"),
        *flags,
    ]
    return grok.main(argv, run=run)


def success_line(out: str) -> str:
    lines = [line for line in out.splitlines() if not line.startswith("ROUTE:")]
    assert len(lines) == 1, out
    return lines[0]


def backups_in(directory: pathlib.Path) -> list[pathlib.Path]:
    return sorted(directory.glob("*.bak-*"))


def unmanaged_text(text: str) -> str:
    return "".join(block.text for block in grok.split_blocks(text) if not block.managed)


def assert_no_secret(*texts: str) -> None:
    for text in texts:
        assert FAKE_VALUE not in text
        assert "api_key" not in text


def expected_block(model_id: str, marker: str = MARKER) -> str:
    model = SEED["models"][model_id]
    endpoint = SEED["endpoints"][model["endpoint"]]
    lines = [
        f"# {marker}",
        f'[model."{model_id}"]',
        f'base_url = "{endpoint["baseUrl"]}"',
        f'model = "{model["remoteId"]}"',
    ]
    if endpoint["auth"] is not None:
        names = ", ".join(
            f'"{name}"'
            for name in (endpoint["auth"]["env"], *endpoint["auth"]["altEnv"])
        )
        lines.append(f"env_key = [{names}]")
    lines.append('api_backend = "chat_completions"')
    lines.append(f"context_window = {model['context']}")
    return "\n".join(lines) + "\n"


# --- rendering ---------------------------------------------------------------------


def test_toml_string_escapes_and_round_trips() -> None:
    value = 'C:\\path "quoted"'
    rendered = grok.toml_string(value)
    assert rendered == '"C:\\\\path \\"quoted\\""'
    assert tomllib.loads(f"k = {rendered}")["k"] == value


def test_render_model_block_for_an_authenticated_endpoint() -> None:
    text = grok.render_model_block(SEED, "glm-5.3", SEED["models"]["glm-5.3"], MARKER)
    assert text == (
        f"# {MARKER}\n"
        '[model."glm-5.3"]\n'
        'base_url = "https://router.huggingface.co/v1"\n'
        'model = "zai-org/GLM-5.3:zai-org"\n'
        'env_key = ["HUGGINGFACE_TOKEN_INFERENCE"]\n'
        'api_backend = "chat_completions"\n'
        "context_window = 131072\n"
    )
    assert tomllib.loads(text)["model"]["glm-5.3"]["env_key"] == [CREDENTIAL]
    assert_no_secret(text)


def test_render_model_block_lists_every_env_name_and_omits_env_key_without_auth() -> (
    None
):
    sidecar = grok.render_model_block(
        SEED, "glm-5.2-free", SEED["models"]["glm-5.2-free"], MARKER
    )
    assert (
        'env_key = ["OPENROUTER_API_KEY_CODEX_SIDECAR", "OPENROUTER_API_KEY_CLI_GRUNT", '
        '"OPENROUTER_API_KEY_IDE_OPENCODE"]\n'
    ) in sidecar
    local = grok.render_model_block(
        SEED, "qwen2.5-7b", SEED["models"]["qwen2.5-7b"], MARKER
    )
    assert local == (
        f"# {MARKER}\n"
        '[model."qwen2.5-7b"]\n'
        'base_url = "http://127.0.0.1:11434/v1"\n'
        'model = "qwen2.5:7b"\n'
        'api_backend = "chat_completions"\n'
        "context_window = 8192\n"
    )
    assert "env_key" not in tomllib.loads(local)["model"]["qwen2.5-7b"]


def test_api_backend_prefers_the_best_ready_wire_and_defaults_to_chat() -> None:
    assert grok.api_backend(SEED, "glm-5.3") == "chat_completions"
    assert grok.api_backend(SEED, "cursor-grok-4.6") == "chat_completions"
    config = seed()
    config["endpoints"]["hf-router"]["wire"]["responses"] = dict(PROBED)
    assert grok.api_backend(config, "glm-5.3") == "responses"
    config["models"]["glm-5.3"]["wire"] = {"responses": "declared"}
    assert grok.api_backend(config, "glm-5.3") == "chat_completions"
    config = seed()
    config["endpoints"]["ollama"]["wire"]["completions"] = "declared"
    config["endpoints"]["ollama"]["wire"]["messages"] = "native"
    assert grok.api_backend(config, "qwen3-8b") == "messages"


def test_render_blocks_one_per_selected_model_without_endpoints_for_the_seed() -> None:
    rendered, endpoints_block = grok.render_blocks(SEED)
    assert tuple(rendered) == GROK_MODELS
    assert endpoints_block is None
    for model_id, text in rendered.items():
        assert text == expected_block(model_id)
        assert common.MANAGED_MARKER_RE.search(text) is not None
        assert_no_secret(text)
    parsed = tomllib.loads("".join(rendered.values()))
    assert set(parsed["model"]) == set(GROK_MODELS)
    for table in parsed["model"].values():
        assert set(table) <= {
            "base_url",
            "model",
            "env_key",
            "api_backend",
            "context_window",
        }


def test_endpoints_block_rendered_only_for_a_probed_bridge() -> None:
    config = probed_seed()
    marker = common.managed_marker(config)
    _, endpoints_block = grok.render_blocks(config)
    assert endpoints_block == (
        f'# {marker}\n[endpoints]\nmodels_base_url = "{BRIDGE_URL}"\n'
    )
    assert tomllib.loads(endpoints_block) == {
        "endpoints": {"models_base_url": BRIDGE_URL}
    }
    declared = seed()
    assert grok.render_endpoints_block(declared, marker) is None
    hand_declared_native = seed()
    hand_declared_native["endpoints"]["cursor-auth2api"]["wire"]["completions"] = (
        "native"
    )
    assert grok.render_endpoints_block(hand_declared_native, marker) is None
    excluded = probed_seed()
    excluded["endpoints"]["cursor-auth2api"]["targets"]["grok"] = "excluded"
    assert grok.render_endpoints_block(excluded, marker) is None


# --- block splitting -----------------------------------------------------------------


def test_split_blocks_preamble_headers_marker_and_odd_headers() -> None:
    assert grok.split_blocks("") == []
    assert grok.split_blocks("# only a comment\n") == [
        grok.Block(None, "# only a comment\n")
    ]
    text = (
        "# preamble\n"
        "[models]\n"
        'default = "x"\n'
        f"{managed_block('glm-5.3')}"
        "[[plugins]]\n"
        'name = "p"\n'
        f"{HAND_WRITTEN_BLOCK}"
        f"{managed_endpoints()}"
    )
    blocks = grok.split_blocks(text)
    assert [(b.header, b.managed, b.model_id) for b in blocks] == [
        (None, False, None),
        ("models", False, None),
        ('model."glm-5.3"', True, "glm-5.3"),
        ("[plugins]", False, None),
        ('model."hand-written"', False, "hand-written"),
        ('model."hand-written".extra_headers', False, None),
        ("endpoints", True, None),
    ]
    assert "".join(block.text for block in blocks) == text
    assert blocks[2].text == managed_block("glm-5.3")
    assert blocks[4].text.startswith('  [model."hand-written"]   # indented')
    assert blocks[6].text == managed_endpoints()


# --- merge semantics -------------------------------------------------------------------


def test_merge_appends_managed_blocks_after_byte_identical_live_content() -> None:
    result = grok.render(SEED, LIVE)
    assert result.text.startswith(LIVE)
    assert unmanaged_text(result.text) == LIVE
    assert result.live_only == ["cursor-grok-4.6"]
    assert result.removed == []
    appended = result.text[len(LIVE) :]
    assert appended == "\n".join(
        expected_block(model_id) for model_id in GROK_MODELS[1:]
    )
    assert grok.render(SEED, LIVE).text == result.text
    assert_no_secret(result.text)


def test_merge_is_idempotent() -> None:
    once = grok.render(SEED, LIVE).text
    twice = grok.render(SEED, once).text
    assert twice == once
    assert grok.render(SEED, twice).text == once
    rendered, endpoints_block = grok.render_blocks(probed_seed())
    first = grok.merge(LIVE, rendered, endpoints_block).text
    assert grok.merge(first, rendered, endpoints_block).text == first


def test_merge_keeps_the_live_only_block_and_drops_the_registry_rendition() -> None:
    result = grok.render(SEED, LIVE)
    assert result.text.count('[model."cursor-grok-4.6"]') == 1
    assert LIVE_ONLY_BLOCK in result.text
    assert expected_block("cursor-grok-4.6") not in result.text
    assert "cursor-grok-4.6" in result.rendered
    parsed = tomllib.loads(result.text)
    assert parsed["model"]["cursor-grok-4.6"]["env_key"] == "CURSOR_AUTH2API_KEY"
    assert parsed["models"] == {"default": "cursor-grok-4.6"}
    assert parsed["plugins"] == [{"name": "first"}]
    assert parsed["model"]["hand-written"]["extra_headers"] == {"X-Trace": "on"}


def test_merge_replaces_stale_managed_blocks_in_place_keeping_their_spacing() -> None:
    live = (
        "[models]\n"
        'default = "glm-5.3"\n'
        "\n"
        f"{managed_block('glm-5.3', STALE_MARKER)}"
        "\n"
        "\n"
        f"{HAND_WRITTEN_BLOCK}"
    )
    result = grok.render(SEED, live)
    assert result.text.startswith(
        '[models]\ndefault = "glm-5.3"\n\n' + expected_block("glm-5.3") + "\n\n"
    )
    assert HAND_WRITTEN_BLOCK in result.text
    assert result.text.index(HAND_WRITTEN_BLOCK) < result.text.index(
        expected_block("cursor-grok-4.6")
    )
    assert STALE_MARKER not in result.text
    assert result.removed == [] and result.live_only == []


def test_merge_removes_managed_blocks_whose_id_left_the_registry() -> None:
    live = (
        "[models]\n"
        'default = "x"\n'
        "\n"
        f"{managed_block('retired')}"
        f"{HAND_WRITTEN_BLOCK}"
        "\n"
        f"{managed_block('also-retired', STALE_MARKER)}"
    )
    result = grok.render(SEED, live)
    assert result.removed == ["retired", "also-retired"]
    assert "retired" not in result.text
    assert HAND_WRITTEN_BLOCK in result.text
    assert unmanaged_text(result.text) == (
        '[models]\ndefault = "x"\n\n' + HAND_WRITTEN_BLOCK + "\n"
    )


def test_merge_preserves_an_unmanaged_model_block_not_in_the_registry() -> None:
    live = HAND_WRITTEN_BLOCK
    result = grok.render(SEED, live)
    assert result.text.startswith(HAND_WRITTEN_BLOCK + "\n# managed-by")
    assert result.live_only == []


def test_merge_endpoints_block_lifecycle() -> None:
    probed = probed_seed()
    rendered, endpoints_block = grok.render_blocks(probed)
    assert endpoints_block is not None
    appended = grok.merge(LIVE, rendered, endpoints_block)
    assert appended.text.endswith("\n" + endpoints_block)
    assert appended.live_only == ["cursor-grok-4.6"]
    stale = grok.merge(
        LIVE + managed_endpoints(STALE_MARKER) + "\n[after]\nk = 1\n",
        rendered,
        endpoints_block,
    )
    assert stale.text.count("[endpoints]") == 1
    assert endpoints_block + "\n[after]\nk = 1\n" in stale.text
    assert stale.removed == []
    hand_written = grok.merge(LIVE + UNMANAGED_ENDPOINTS, rendered, endpoints_block)
    assert hand_written.text.count("[endpoints]") == 1
    assert UNMANAGED_ENDPOINTS in hand_written.text
    assert hand_written.live_only == ["cursor-grok-4.6", "endpoints"]
    declared_rendered, none_block = grok.render_blocks(SEED)
    assert none_block is None
    purged = grok.merge(LIVE + managed_endpoints(), declared_rendered, None)
    assert "[endpoints]" not in purged.text
    assert purged.removed == ["endpoints"]
    untouched = grok.merge(LIVE + UNMANAGED_ENDPOINTS, declared_rendered, None)
    assert UNMANAGED_ENDPOINTS in untouched.text
    assert untouched.live_only == ["cursor-grok-4.6"]
    for merged in (appended, stale, hand_written, purged, untouched):
        tomllib.loads(merged.text)


def test_merge_separators_for_files_without_a_trailing_newline() -> None:
    absent = grok.render(SEED, None)
    assert absent.text.startswith(expected_block("cursor-grok-4.6") + "\n")
    assert absent.text == "\n".join(expected_block(m) for m in GROK_MODELS)
    unterminated = grok.render(SEED, '[models]\ndefault = "x"')
    assert unterminated.text.startswith('[models]\ndefault = "x"\n\n# managed-by')
    last_block = grok.render(SEED, managed_block("glm-5.3").rstrip("\n"))
    assert last_block.text.startswith(expected_block("glm-5.3") + "\n")
    for merged in (absent, unterminated, last_block):
        tomllib.loads(merged.text)


def test_render_refuses_a_live_file_or_a_merge_that_does_not_parse() -> None:
    with pytest.raises(grok.GrokMergeError, match="^live config does not parse") as bad:
        grok.render(SEED, "[models\n")
    assert "refusing to merge into it" in str(bad.value)
    with pytest.raises(
        grok.GrokMergeError, match="^merged config does not parse as TOML"
    ):
        grok.render(SEED, 'model = "a scalar where the model table must go"\n')


# --- dry run, routing report, check ----------------------------------------------------


def test_dry_run_reports_counts_and_every_routing_decision(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path) == 0
    out = capsys.readouterr().out
    routes = [line for line in out.splitlines() if line.startswith("ROUTE:grok ")]
    assert len(routes) == len(SEED["endpoints"])
    assert EXCLUDED_ROUTE in routes
    assert INCLUDED_ROUTE in routes
    assert success_line(out) == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=false "
        "removed=0 live_only=0 changed=true"
    )
    assert not (tmp_path / "grok").exists()
    assert_no_secret(out)


def test_dry_run_against_a_live_file_changes_nothing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    path.write_bytes(LIVE.encode("utf-8"))
    assert run_main(tmp_path, "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=false "
        "removed=0 live_only=1 changed=true\n"
    )
    assert path.read_bytes() == LIVE.encode("utf-8")
    assert backups_in(path.parent) == []


def test_quiet_hides_the_routing_report(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--quiet") == 0
    out = capsys.readouterr().out
    assert "ROUTE:" not in out
    assert out.startswith("SUCCESS:grok-models-merge ")


def test_check_reports_drift_then_passes_after_write(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--check", "--quiet") == 1
    assert capsys.readouterr().out == (
        "FAILED:grok-models-merge check drift=config.toml\n"
    )
    assert not (tmp_path / "grok").exists()
    assert run_main(tmp_path, "--write", "--quiet") == 0
    capsys.readouterr()
    assert run_main(tmp_path, "--check", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=false "
        "removed=0 live_only=0 changed=false\n"
    )
    path = live_file(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8") + "\n" + managed_block("retired"),
        encoding="utf-8",
    )
    assert run_main(tmp_path, "--check", "--quiet") == 1
    assert capsys.readouterr().out == (
        "FAILED:grok-models-merge check drift=config.toml\n"
    )


# --- write ---------------------------------------------------------------------------


def test_write_creates_the_file_and_is_idempotent(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=true "
        "removed=0 live_only=0 changed=true\n"
    )
    path = live_file(tmp_path)
    first = path.read_bytes()
    assert first == "\n".join(expected_block(m) for m in GROK_MODELS).encode("utf-8")
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=false "
        "removed=0 live_only=0 changed=false\n"
    )
    assert path.read_bytes() == first
    assert backups_in(path.parent) == []
    parsed = tomllib.loads(first.decode("utf-8"))
    assert set(parsed) == {"model"}
    assert_no_secret(first.decode("utf-8"))


def test_write_merges_into_a_live_file_with_a_backup(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    original = (LIVE + managed_block("retired") + "\n" + UNMANAGED_ENDPOINTS).encode(
        "utf-8"
    )
    path.write_bytes(original)
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=true "
        "removed=1 live_only=1 changed=true\n"
    )
    merged = path.read_text(encoding="utf-8")
    assert merged.startswith(LIVE)
    assert "retired" not in merged
    assert LIVE_ONLY_BLOCK in merged
    assert UNMANAGED_ENDPOINTS in merged
    assert unmanaged_text(merged) == LIVE + UNMANAGED_ENDPOINTS + "\n"
    backups = backups_in(path.parent)
    assert [p.name.split(".bak-")[0] for p in backups] == ["config.toml"]
    assert backups[0].read_bytes() == original
    assert_no_secret(merged)


def test_write_no_backup_leaves_no_bak_files(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    path.write_text(LIVE, encoding="utf-8")
    assert run_main(tmp_path, "--write", "--no-backup", "--quiet") == 0
    assert "written=true removed=0 live_only=1 changed=true" in capsys.readouterr().out
    assert backups_in(path.parent) == []
    assert path.read_text(encoding="utf-8").startswith(LIVE)


def test_write_renders_the_endpoints_block_once_the_bridge_is_probed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    path.write_text(LIVE, encoding="utf-8")
    config = probed_seed()
    registry = write_registry(tmp_path, config)
    assert run_main(tmp_path, "--write", "--quiet", registry=registry) == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=true written=true "
        "removed=0 live_only=1 changed=true\n"
    )
    merged = path.read_text(encoding="utf-8")
    parsed = tomllib.loads(merged)
    assert parsed["endpoints"] == {"models_base_url": BRIDGE_URL}
    assert merged.endswith(
        f"# {common.managed_marker(config)}\n[endpoints]\n"
        f'models_base_url = "{BRIDGE_URL}"\n'
    )
    assert run_main(tmp_path, "--write", "--quiet") == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=true "
        "removed=1 live_only=1 changed=true\n"
    )
    assert "[endpoints]" not in path.read_text(encoding="utf-8")
    assert len(backups_in(path.parent)) == 2


def test_write_reflects_registry_changes_by_removing_managed_blocks(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_main(tmp_path, "--write", "--quiet") == 0
    config = seed()
    config["endpoints"]["ollama"]["targets"]["grok"] = "excluded"
    registry = write_registry(tmp_path, config)
    assert run_main(tmp_path, "--write", "--quiet", registry=registry) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "SUCCESS:grok-models-merge models=3 endpoints_block=false written=true "
        "removed=3 live_only=0 changed=true"
    )
    merged = live_file(tmp_path).read_text(encoding="utf-8")
    assert "qwen" not in merged
    assert set(tomllib.loads(merged)["model"]) == set(GROK_MODELS[:3])


# --- smoke + rollback ------------------------------------------------------------------


def test_smoke_pass_keeps_the_write_and_points_grok_home_at_the_live_directory(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = FakeRun(returncode=0)
    assert run_main(tmp_path, "--write", "--smoke", "--quiet", run=run) == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=true "
        "removed=0 live_only=0 changed=true smoke=true\n"
    )
    cmd, kwargs = run.calls[0]
    assert cmd == ["grok", "inspect"]
    assert kwargs["env"]["GROK_HOME"] == str(tmp_path / "grok")
    assert kwargs["env"][CREDENTIAL] == FAKE_VALUE
    assert live_file(tmp_path).exists()


def test_smoke_failure_restores_the_live_file_byte_for_byte(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    original = LIVE.replace("\n", "\r\n").encode("utf-8")
    path.write_bytes(original)
    run = FakeRun(returncode=1)
    assert run_main(tmp_path, "--write", "--smoke", "--quiet", run=run) == 2
    out = capsys.readouterr().out
    assert out == (
        f"FAILED:grok-models-merge smoke 'grok inspect' failed; {path} restored\n"
    )
    assert_no_secret(out)
    assert path.read_bytes() == original
    assert len(backups_in(path.parent)) == 1


# --- failures ------------------------------------------------------------------------------


def test_invalid_registry_fails_closed(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = seed()
    config["endpoints"]["hf-router"]["targets"]["grok"] = "sometimes"
    registry = write_registry(tmp_path, config)
    assert run_main(tmp_path, "--write", registry=registry) == 2
    out = capsys.readouterr().out
    assert out.startswith("FAILED:grok-models-merge hf-router: targets.grok")
    assert "ROUTE:" not in out
    assert not (tmp_path / "grok").exists()


def test_unparseable_live_file_fails_before_anything_is_written(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = live_file(tmp_path)
    path.write_text("[models\n", encoding="utf-8")
    assert run_main(tmp_path, "--write") == 2
    out = capsys.readouterr().out
    assert out.startswith(
        "FAILED:grok-models-merge live config does not parse as TOML; refusing to "
        "merge into it ("
    )
    assert path.read_text(encoding="utf-8") == "[models\n"
    assert backups_in(path.parent) == []


def test_a_credential_value_in_the_render_fails_by_name_only(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv(CREDENTIAL, "router.huggingface.co")
    assert run_main(tmp_path, "--write") == 2
    assert capsys.readouterr().out == (
        "FAILED:grok-models-merge rendered text contains the value of "
        "HUGGINGFACE_TOKEN_INFERENCE (len=21); credentials are referenced by name "
        "only (L6)\n"
    )
    assert not (tmp_path / "grok").exists()


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
            str(tmp_path / "grok" / "config.toml"),
            "--quiet",
        ],
    )
    with pytest.raises(SystemExit) as info:
        runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
    assert info.value.code == 0
    assert capsys.readouterr().out == (
        "SUCCESS:grok-models-merge models=6 endpoints_block=false written=false "
        "removed=0 live_only=0 changed=true\n"
    )


def test_default_live_is_the_users_grok_config_toml() -> None:
    parser = common.build_parser(grok.NAME, default_live=grok.DEFAULT_LIVE_CONFIG)
    assert parser.parse_args([]).live == r"%USERPROFILE%\.grok\config.toml"
    assert grok.SMOKE_COMMAND == ("grok", "inspect")
    assert grok.MODEL_HEADER_RE.pattern == r'^\[model\."(?P<id>[^"]+)"\]$'
