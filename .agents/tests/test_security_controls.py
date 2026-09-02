"""WU-10 security controls: L0 path-exists check, OpenRouter request hardening,
and the ``INFERENCE_HALT`` kill switch.

The scripts are flat files, so every module is loaded by path (the same idiom as
``test_mcp_control_plane.py``); ``openrouter-complete.py`` carries a hyphen and is
registered under ``openrouter_complete``. ``inference_halt`` is registered under its
own name so ``--cov=inference_halt`` measures it.
"""

from __future__ import annotations

import copy
import datetime
import importlib.util
import io
import json
import pathlib
import runpy
import sys
import urllib.error
from typing import Any

import pytest


AGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO_ROOT = AGENTS_ROOT.parent
SCRIPTS_ROOT = AGENTS_ROOT / "scripts"
TOOLCHAIN_PREFIX = r"C:\Users\Prekzursil\source\agent-skills-toolchain"
FAKE_SECRET = "FAKE_OR_VALUE_NOT_A_KEY"
TODAY = datetime.date(2026, 9, 2)


def load_script(name: str, filename: str | None = None) -> Any:
    path = SCRIPTS_ROOT / (filename or f"{name}.py")
    assert path.is_file(), f"missing script: {path}"
    if str(SCRIPTS_ROOT) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_ROOT))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def registry(servers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    for server in servers.values():
        server.setdefault("credentialNames", [])
        server.setdefault("tags", ["test"])
    return {
        "schemaVersion": 1,
        "mcp": {
            "policy": {
                "required": False,
                "startupTimeoutMs": 30_000,
                "toolTimeoutMs": 30_000,
                "healthProbe": {"kind": "mcp-tools-list", "timeoutMs": 30_000},
                "toolAllowlist": ["*"],
                "approvalMode": "native",
                "maxPrivateBytes": 512 * 1024 * 1024,
            },
            "supervision": {
                "totalIdlePrivateBytes": 6 * 1024 * 1024 * 1024,
                "failureThreshold": 3,
                "failureWindowSeconds": 600,
                "quarantineScope": "session",
                "duplicatePolicy": "report-unless-exact-process-tree",
            },
            "servers": servers,
        },
    }


def stdio_server(command: str, *args: str, **extra: Any) -> dict[str, Any]:
    server: dict[str, Any] = {
        "enabled": True,
        "targets": ["claude"],
        "transport": "stdio",
        "command": command,
        "args": list(args),
    }
    server.update(extra)
    return server


# --------------------------------------------------------------------------
# validate_mcp_control_plane.py --check-paths
# --------------------------------------------------------------------------


def paths_fixture(tmp_path: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """A registry whose mapped paths resolve under ``tmp_path/root``.

    Expected with the missing directory absent:
    checked=4 (present script, missing dir, mixed-case forward-slash script, bare
    prefix), missing=1, unmapped=6 (three interpreter commands, the relative
    ``mcp_server.py``, and both paths of the ``.local`` server).
    """
    root = tmp_path / "root"
    (root / "tools" / "mcp" / "present").mkdir(parents=True)
    (root / "tools" / "mcp" / "present" / "server.py").write_text(
        "print('present')\n", encoding="utf-8"
    )
    config = registry(
        {
            "present-script": stdio_server(
                r"C:\Python314\python.exe",
                TOOLCHAIN_PREFIX + r"\tools\mcp\present\server.py",
            ),
            "missing-dir": stdio_server(
                r"C:\Users\Prekzursil\.local\bin\uv.exe",
                "run",
                "--locked",
                "--directory",
                TOOLCHAIN_PREFIX + r"\tools\mcp\missing-dir",
                "python",
                "mcp_server.py",
            ),
            "local-only": stdio_server(
                r"C:\Users\Prekzursil\.local\opt\tool\.venv\Scripts\python.exe",
                r"C:\Users\Prekzursil\.local\opt\tool\server.py",
            ),
            "forward-slash": stdio_server(
                "C:/Python314/python.exe",
                "c:/users/prekzursil/SOURCE/agent-skills-toolchain/tools/mcp/present/server.py",
            ),
            "root-dir": stdio_server("uv", "run", "--directory", TOOLCHAIN_PREFIX),
            "bare-command": stdio_server("npx", "-y", "example-mcp@latest"),
            "disabled-missing": stdio_server(
                "uv",
                "--directory",
                TOOLCHAIN_PREFIX + r"\tools\mcp\never-checked",
                enabled=False,
            ),
            "remote": {
                "enabled": True,
                "targets": ["claude"],
                "transport": "http",
                "url": "http://127.0.0.1:8812/mcp/",
            },
        }
    )
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path, root


def run_validate(
    capsys: pytest.CaptureFixture[str],
    config_path: pathlib.Path,
    *extra: str,
) -> tuple[int, str]:
    validate = load_script("validate_mcp_control_plane")
    rc = validate.main(
        [
            "--agents-config",
            str(config_path),
            "--rotation-manifest",
            str(config_path.parent / "absent-manifest.json"),
            *extra,
        ]
    )
    return rc, capsys.readouterr().out


EXPECTED_DEFAULT_LINE = (
    "SUCCESS:mcp-control-plane-validate servers=8 claude_targets=7 codex_targets=0 "
    "rotation_providers=0 rotation_policy=never\n"
)


def test_default_output_is_unchanged_without_the_flag(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path, _root = paths_fixture(tmp_path)

    rc, out = run_validate(capsys, config_path)

    assert rc == 0
    assert out == EXPECTED_DEFAULT_LINE
    assert "PATHS:" not in out


def test_check_paths_reports_the_missing_directory_and_stays_report_only(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path, root = paths_fixture(tmp_path)

    rc, out = run_validate(capsys, config_path, "--check-paths", "--root", str(root))

    assert rc == 0
    assert out == (
        "PATHS:mcp-registry checked=4 missing=1 unmapped=6 missing_servers=missing-dir\n"
        + EXPECTED_DEFAULT_LINE
    )


def test_check_paths_is_clean_once_the_directory_exists(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path, root = paths_fixture(tmp_path)
    (root / "tools" / "mcp" / "missing-dir").mkdir()

    rc, out = run_validate(capsys, config_path, "--check-paths", "--root", str(root))

    assert rc == 0
    assert out.splitlines()[0] == (
        "PATHS:mcp-registry checked=4 missing=0 unmapped=6 missing_servers="
    )
    assert out.endswith(EXPECTED_DEFAULT_LINE)


def test_check_paths_strict_exits_3_only_while_something_is_missing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_path, root = paths_fixture(tmp_path)

    rc, out = run_validate(
        capsys, config_path, "--check-paths-strict", "--root", str(root)
    )
    assert rc == 3
    lines = out.splitlines()
    assert lines[0].startswith("PATHS:mcp-registry checked=4 missing=1 ")
    assert lines[1] == (
        "FAILED:mcp-control-plane-validate paths_missing=1 missing_servers=missing-dir"
    )
    assert "SUCCESS:" not in out

    (root / "tools" / "mcp" / "missing-dir").mkdir()
    rc, out = run_validate(
        capsys,
        config_path,
        "--check-paths",
        "--check-paths-strict",
        "--root",
        str(root),
    )
    assert rc == 0
    assert out.endswith(EXPECTED_DEFAULT_LINE)


def test_check_paths_defaults_to_the_windows_toolchain_root(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    validate = load_script("validate_mcp_control_plane")
    config_path, _root = paths_fixture(tmp_path)
    assert validate.DEFAULT_TOOLCHAIN_ROOT == pathlib.Path(TOOLCHAIN_PREFIX)
    if validate.DEFAULT_TOOLCHAIN_ROOT.is_dir():
        pytest.skip("running on the box: the default root is the live checkout")

    rc, out = run_validate(capsys, config_path, "--check-paths")

    assert rc == 0
    assert out.splitlines()[0] == (
        "PATHS:mcp-registry checked=4 missing=4 unmapped=6 "
        "missing_servers=forward-slash,missing-dir,present-script,root-dir"
    )


def test_map_toolchain_path_handles_both_slash_forms_case_and_siblings(
    tmp_path: pathlib.Path,
) -> None:
    validate = load_script("validate_mcp_control_plane")

    assert validate.map_toolchain_path(TOOLCHAIN_PREFIX, tmp_path) == tmp_path
    assert validate.map_toolchain_path(TOOLCHAIN_PREFIX + "\\", tmp_path) == tmp_path
    assert (
        validate.map_toolchain_path(TOOLCHAIN_PREFIX + r"\tools\mcp\x\y.py", tmp_path)
        == tmp_path / "tools" / "mcp" / "x" / "y.py"
    )
    assert (
        validate.map_toolchain_path(
            "c:/USERS/prekzursil/source/agent-skills-toolchain/tools//z.mjs", tmp_path
        )
        == tmp_path / "tools" / "z.mjs"
    )
    assert validate.map_toolchain_path(TOOLCHAIN_PREFIX + r"-2\x.py", tmp_path) is None
    assert validate.map_toolchain_path(r"C:\Python314\python.exe", tmp_path) is None
    assert validate.map_toolchain_path("mcp_server.py", tmp_path) is None


def test_candidate_paths_follow_the_documented_selection_rule() -> None:
    validate = load_script("validate_mcp_control_plane")

    assert validate.candidate_paths(stdio_server("npx", "-y", "pkg@latest")) == []
    assert validate.candidate_paths(
        stdio_server(
            r"C:\Python314\python.exe",
            "--directory",
            r"D:\somewhere",
            "--flag",
            "Server.PS1",
            "loader.mjs",
            "tool.js",
            "notes.txt",
        )
    ) == [
        r"C:\Python314\python.exe",
        r"D:\somewhere",
        "Server.PS1",
        "loader.mjs",
        "tool.js",
    ]
    assert validate.candidate_paths(stdio_server("uv", "--directory")) == []
    assert validate.candidate_paths({"transport": "stdio"}) == []


def test_check_registry_paths_exposes_missing_pairs_for_programmatic_use(
    tmp_path: pathlib.Path,
) -> None:
    validate = load_script("validate_mcp_control_plane")
    config_path, root = paths_fixture(tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))

    report = validate.check_registry_paths(config, root)

    assert report.checked == 4
    assert report.unmapped == 6
    assert report.missing == (
        ("missing-dir", str(root / "tools" / "mcp" / "missing-dir")),
    )
    assert report.missing_servers == ["missing-dir"]
    assert validate.format_paths_line(report) == (
        "PATHS:mcp-registry checked=4 missing=1 unmapped=6 missing_servers=missing-dir"
    )


GLM53_SPACE_ROW = {
    "enabled": True,
    "targets": ["claude"],
    "transport": "stdio",
    "command": r"C:\Users\Prekzursil\.local\bin\uv.exe",
    "args": [
        "run",
        "--locked",
        "--directory",
        TOOLCHAIN_PREFIX + r"\tools\mcp\glm53-space",
        "python",
        "mcp_server.py",
    ],
    "credentialNames": [],
    "tags": ["fixture", "owner-requested"],
}


def test_acceptance_real_registry_reports_exactly_glm53_space_as_missing(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """WU-10 acceptance: the live registry against the repo checkout.

    The fixture is a copy of the live ``agents.json`` that KEEPS the
    ``glm53-space`` row (D1 deletes it from the live file later), so the check
    keeps proving it can see registry rows whose code git does not hold.
    """
    live = json.loads((AGENTS_ROOT / "agents.json").read_text(encoding="utf-8"))
    fixture = copy.deepcopy(live)
    fixture["mcp"]["servers"].setdefault("glm53-space", copy.deepcopy(GLM53_SPACE_ROW))
    assert fixture["mcp"]["servers"]["glm53-space"]["args"][2:4] == [
        "--directory",
        TOOLCHAIN_PREFIX + r"\tools\mcp\glm53-space",
    ]
    assert not (REPO_ROOT / "tools" / "mcp" / "glm53-space").exists()
    config_path = tmp_path / "agents.json"
    config_path.write_text(json.dumps(fixture), encoding="utf-8")

    rc, out = run_validate(
        capsys, config_path, "--check-paths", "--root", str(REPO_ROOT)
    )

    assert rc == 0
    paths_line = out.splitlines()[0]
    fields = dict(token.split("=", 1) for token in paths_line.split()[1:])
    assert paths_line.startswith("PATHS:mcp-registry ")
    assert fields["missing"] == "1"
    assert fields["missing_servers"] == "glm53-space"
    assert int(fields["checked"]) >= 2
    assert int(fields["unmapped"]) >= 1
    assert "SUCCESS:mcp-control-plane-validate" in out


# --------------------------------------------------------------------------
# openrouter-complete.py
# --------------------------------------------------------------------------


def load_openrouter() -> Any:
    return load_script("openrouter_complete", "openrouter-complete.py")


def test_request_body_requires_parameters_only_with_tools_or_response_format() -> None:
    openrouter = load_openrouter()
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    schema = {"type": "json_object"}

    plain = openrouter.build_request_body("m", "p", 8)
    with_tools = openrouter.build_request_body("m", "p", 8, tools=tools)
    with_schema = openrouter.build_request_body("m", "p", 8, response_format=schema)
    with_both = openrouter.build_request_body(
        "m", "p", 8, tools=tools, response_format=schema
    )

    assert "require_parameters" not in plain["provider"]
    assert "tools" not in plain and "response_format" not in plain
    assert with_tools["tools"] == tools
    assert with_tools["provider"]["require_parameters"] is True
    assert with_schema["response_format"] == schema
    assert with_schema["provider"]["require_parameters"] is True
    assert with_both["provider"] == {
        "require_parameters": True,
        "data_collection": "deny",
    }


def test_request_body_data_collection_is_denied_by_default_and_can_be_allowed() -> None:
    openrouter = load_openrouter()

    denied = openrouter.build_request_body("m", "pong", 32)
    allowed = openrouter.build_request_body("m", "pong", 32, deny_data_collection=False)

    assert denied["provider"] == {"data_collection": "deny"}
    assert "provider" not in allowed
    assert allowed == {
        "model": "m",
        "messages": [{"role": "user", "content": "pong"}],
        "max_tokens": 32,
        "temperature": 0,
    }
    assert list(denied)[:4] == ["model", "messages", "max_tokens", "temperature"]


def completion_payload() -> dict[str, Any]:
    return {
        "id": "gen-fixture",
        "model": "vendor/model",
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
        "choices": [{"message": {"content": "pong"}}],
    }


def test_cli_default_denies_data_collection_and_never_prints_the_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    openrouter = load_openrouter()
    seen: dict[str, Any] = {}

    def fake_request(
        method: str, url: str, secret: str, body: Any = None, timeout: int = 90
    ) -> tuple[int, object]:
        seen.update(method=method, url=url, secret=secret, body=body)
        return 200, completion_payload()

    monkeypatch.setattr(openrouter, "request", fake_request)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_SECRET)

    rc = openrouter.main(["--model", "vendor/model", "--skip-generation"])

    captured = capsys.readouterr()
    assert rc == 0
    assert seen["secret"] == FAKE_SECRET
    assert seen["body"]["provider"] == {"data_collection": "deny"}
    assert "tools" not in seen["body"]
    assert FAKE_SECRET not in captured.out + captured.err
    assert "response_snippet=pong" in captured.out


def test_cli_json_flags_add_require_parameters_and_opt_out_of_denial(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    openrouter = load_openrouter()
    seen: dict[str, Any] = {}

    def fake_request(
        method: str, url: str, secret: str, body: Any = None, timeout: int = 90
    ) -> tuple[int, object]:
        seen["body"] = body
        return 200, completion_payload()

    monkeypatch.setattr(openrouter, "request", fake_request)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_SECRET)

    rc = openrouter.main(
        [
            "--skip-generation",
            "--allow-data-collection",
            "--tools-json",
            '[{"type": "function", "function": {"name": "f", "parameters": {}}}]',
            "--response-format-json",
            '{"type": "json_object"}',
        ]
    )

    assert rc == 0
    assert seen["body"]["provider"] == {"require_parameters": True}
    assert seen["body"]["tools"][0]["function"]["name"] == "f"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert FAKE_SECRET not in capsys.readouterr().out


def test_cli_rejects_malformed_json_flags_before_any_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    openrouter = load_openrouter()
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_SECRET)
    monkeypatch.setattr(
        openrouter, "request", lambda *a, **k: pytest.fail("request must not run")
    )

    with pytest.raises(SystemExit) as excinfo:
        openrouter.main(["--tools-json", "{not json"])

    assert excinfo.value.code == 2
    assert FAKE_SECRET not in capsys.readouterr().err


def fake_models() -> list[dict[str, Any]]:
    aa = "artificial_analysis"
    return [
        {
            "id": "vendor/top",
            "benchmarks": {aa: {"intelligence_index": 70.0, "coding_index": 10.0}},
            "expiration_date": None,
            "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        },
        {
            "id": "vendor/expiring",
            "benchmarks": {aa: {"intelligence_index": 99.0}},
            "expiration_date": "2026-09-20",
        },
        {
            "id": "vendor/bad-date",
            "benchmarks": {aa: {"intelligence_index": 98.0}},
            "expiration_date": "soon",
        },
        {
            "id": "vendor/int-date",
            "benchmarks": {aa: {"intelligence_index": 97.0}},
            "expiration_date": 20260920,
        },
        {
            "id": "vendor/retired",
            "benchmarks": {aa: {"intelligence_index": 96.0}},
            "status": "deprecated",
        },
        {
            "id": "vendor/tie-b",
            "benchmarks": {aa: {"intelligence_index": 50.0}},
            "expiration_date": "2098-12-31",
        },
        {
            "id": "vendor/live-explicit",
            "benchmarks": {aa: {"intelligence_index": 50.0}},
            "status": "live",
        },
        {
            "id": "vendor/horizon-edge",
            "benchmarks": {aa: {"intelligence_index": 40.0, "coding_index": 90.0}},
            "expiration_date": "2026-10-02",
        },
        {"id": "vendor/flat-score", "benchmarks": {aa: 55}},
        {"id": "vendor/bool-score", "benchmarks": {aa: {"intelligence_index": True}}},
        {"id": "vendor/unscored", "benchmarks": {"design_arena": []}},
        {"id": "vendor/no-benchmarks", "pricing": "free"},
    ]


def test_rank_models_orders_by_the_index_and_skips_expiring_and_non_live() -> None:
    openrouter = load_openrouter()

    report = openrouter.rank_models(fake_models(), 10, TODAY)

    assert [m.id for m in report.ranked] == [
        "vendor/top",
        "vendor/flat-score",
        "vendor/live-explicit",
        "vendor/tie-b",
        "vendor/horizon-edge",
    ]
    assert [m.score for m in report.ranked] == [70.0, 55.0, 50.0, 50.0, 40.0]
    assert report.candidates == 12
    assert report.scored == 5
    assert report.skipped_expiring == 3
    assert report.skipped_not_live == 1
    assert report.ranked[0].prompt_price == "0.000001"
    assert report.ranked[0].completion_price == "0.000002"
    assert report.ranked[0].expiration_date is None
    assert report.ranked[3].expiration_date == "2098-12-31"
    assert report.ranked[1].prompt_price is None


def test_rank_models_truncates_to_n_and_honours_another_index() -> None:
    openrouter = load_openrouter()

    top_two = openrouter.rank_models(fake_models(), 2, TODAY)
    coding = openrouter.rank_models(fake_models(), 3, TODAY, index="coding_index")

    assert [m.id for m in top_two.ranked] == ["vendor/top", "vendor/flat-score"]
    assert top_two.scored == 5
    assert [m.id for m in coding.ranked] == [
        "vendor/horizon-edge",
        "vendor/flat-score",
        "vendor/top",
    ]
    assert openrouter.rank_models([], 5, TODAY).ranked == ()


def test_model_predicates_cover_the_edge_cases() -> None:
    openrouter = load_openrouter()

    assert openrouter.model_is_live({"id": "x"}) is True
    assert openrouter.model_is_live({"id": "x", "status": "live"}) is True
    assert openrouter.model_is_live({"id": "x", "status": "beta"}) is False
    assert openrouter.model_expires_soon({"id": "x"}, TODAY) is False
    assert openrouter.model_expires_soon({"expiration_date": "2026-10-01"}, TODAY)
    assert not openrouter.model_expires_soon({"expiration_date": "2026-10-02"}, TODAY)
    assert openrouter.model_expires_soon({"expiration_date": "2026-01-01"}, TODAY)
    assert openrouter.model_expires_soon(
        {"expiration_date": "2026-09-30T00:00:00Z"}, TODAY
    )
    assert (
        openrouter.model_score({"benchmarks": {"artificial_analysis": 7}}, "any") == 7
    )
    assert openrouter.model_score({"benchmarks": []}, "intelligence_index") is None
    assert openrouter.model_score({"benchmarks": {}}, "intelligence_index") is None


def test_rank_cli_is_keyless_prints_top_n_and_never_prints_the_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    openrouter = load_openrouter()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        openrouter, "request", lambda *a, **k: pytest.fail("rank must not call request")
    )
    monkeypatch.setattr(openrouter, "_today", lambda: TODAY)

    rc = openrouter.main(["--rank", "--top", "3"], fetch_models=fake_models)

    out = capsys.readouterr().out
    assert rc == 0
    assert out.splitlines() == [
        "rank_source=https://openrouter.ai/api/v1/models",
        "rank_index=intelligence_index",
        "rank_candidates=12",
        "rank_scored=5",
        "rank_skipped_expiring=3",
        "rank_skipped_not_live=1",
        "rank=1 model=vendor/top intelligence_index=70.0 expiration_date=- "
        "prompt_price=0.000001 completion_price=0.000002",
        "rank=2 model=vendor/flat-score intelligence_index=55.0 expiration_date=- "
        "prompt_price=- completion_price=-",
        "rank=3 model=vendor/live-explicit intelligence_index=50.0 expiration_date=- "
        "prompt_price=- completion_price=-",
    ]

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_SECRET)
    rc = openrouter.main(
        ["--rank", "--rank-index", "coding_index", "--top", "1"],
        fetch_models=fake_models,
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert FAKE_SECRET not in captured.out + captured.err
    assert "rank=1 model=vendor/horizon-edge coding_index=90.0" in captured.out


def test_rank_cli_uses_the_catalog_fetcher_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    openrouter = load_openrouter()
    monkeypatch.setattr(openrouter, "fetch_models_catalog", fake_models)
    monkeypatch.setattr(openrouter, "_today", lambda: TODAY)

    rc = openrouter.main(["--rank", "--top", "1"])

    assert rc == 0
    assert "rank=1 model=vendor/top " in capsys.readouterr().out


def test_rank_cli_reports_fetch_failures_with_exit_3(
    capsys: pytest.CaptureFixture[str],
) -> None:
    openrouter = load_openrouter()

    def failing_fetch() -> list[dict[str, Any]]:
        raise urllib.error.URLError("simulated outage")

    rc = openrouter.main(["--rank"], fetch_models=failing_fetch)

    captured = capsys.readouterr()
    assert rc == 3
    assert "ERROR rank: " in captured.err
    assert "simulated outage" in captured.err
    assert "rank=1" not in captured.out


class FakeResponse(io.BytesIO):
    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def test_fetch_models_catalog_reads_the_keyless_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter = load_openrouter()
    seen: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: int = 0) -> FakeResponse:
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["timeout"] = timeout
        return FakeResponse(json.dumps({"data": fake_models()}).encode("utf-8"))

    monkeypatch.setattr(openrouter.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_SECRET)

    models = openrouter.fetch_models_catalog()

    assert [m["id"] for m in models][:2] == ["vendor/top", "vendor/expiring"]
    assert seen["url"] == "https://openrouter.ai/api/v1/models"
    assert seen["timeout"] == 30
    assert not any(name.lower() == "authorization" for name in seen["headers"])
    assert FAKE_SECRET not in json.dumps(seen)


def test_fetch_models_catalog_rejects_a_payload_without_a_data_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    openrouter = load_openrouter()
    monkeypatch.setattr(
        openrouter.urllib.request,
        "urlopen",
        lambda req, timeout=0: FakeResponse(b'{"data": {"not": "a list"}}'),
    )

    with pytest.raises(ValueError, match="data list"):
        openrouter.fetch_models_catalog(timeout=5)


def test_today_is_the_utc_calendar_date() -> None:
    openrouter = load_openrouter()

    utc_today = datetime.datetime.now(datetime.timezone.utc).date()
    assert abs((openrouter._today() - utc_today).days) <= 1


# --------------------------------------------------------------------------
# inference_halt.py
# --------------------------------------------------------------------------


def load_halt() -> Any:
    return load_script("inference_halt")


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE", " Yes "])
def test_env_values_that_halt(value: str, tmp_path: pathlib.Path) -> None:
    halt = load_halt()

    assert halt.is_halted(environ={"INFERENCE_HALT": value}, repo_root=tmp_path)
    assert halt.halt_reason(environ={"INFERENCE_HALT": value}, repo_root=tmp_path) == (
        f"env INFERENCE_HALT={value.strip()}"
    )


@pytest.mark.parametrize("value", ["0", "false", "", "no", "maybe"])
def test_env_values_that_do_not_halt(value: str, tmp_path: pathlib.Path) -> None:
    halt = load_halt()

    assert (
        halt.is_halted(environ={"INFERENCE_HALT": value}, repo_root=tmp_path) is False
    )
    assert (
        halt.halt_reason(environ={"INFERENCE_HALT": value}, repo_root=tmp_path) is None
    )


def test_halt_file_halts_with_its_first_line_as_the_reason(
    tmp_path: pathlib.Path,
) -> None:
    halt = load_halt()
    path = tmp_path / ".agents" / "INFERENCE-HALT"
    assert halt.halt_file(tmp_path) == path
    assert halt.is_halted(environ={}, repo_root=tmp_path) is False

    path.parent.mkdir()
    path.write_text("\n  budget blown  \nsecond line ignored\n", encoding="utf-8")

    assert halt.is_halted(environ={}, repo_root=tmp_path) is True
    assert halt.halt_reason(environ={}, repo_root=tmp_path) == (
        f"file {path}: budget blown"
    )

    path.write_text("   \n", encoding="utf-8")
    assert halt.halt_reason(environ={}, repo_root=tmp_path) == (
        f"file {path}: no reason recorded"
    )


def test_env_takes_precedence_over_the_file(tmp_path: pathlib.Path) -> None:
    halt = load_halt()
    halt.set_halt("file reason", repo_root=tmp_path)

    assert halt.halt_reason(environ={"INFERENCE_HALT": "1"}, repo_root=tmp_path) == (
        "env INFERENCE_HALT=1"
    )
    assert halt.halt_reason(environ={"INFERENCE_HALT": "0"}, repo_root=tmp_path) == (
        f"file {halt.halt_file(tmp_path)}: file reason"
    )


def test_set_and_clear_round_trip(tmp_path: pathlib.Path) -> None:
    halt = load_halt()

    written = halt.set_halt("owner: pause spend", repo_root=tmp_path)

    assert written == tmp_path / ".agents" / "INFERENCE-HALT"
    assert written.read_text(encoding="utf-8") == "owner: pause spend\n"
    assert halt.is_halted(environ={}, repo_root=tmp_path) is True
    assert halt.clear_halt(repo_root=tmp_path) is True
    assert not written.exists()
    assert halt.is_halted(environ={}, repo_root=tmp_path) is False
    assert halt.clear_halt(repo_root=tmp_path) is False
    assert sorted(p.name for p in (tmp_path / ".agents").iterdir()) == []


def test_default_repo_root_is_the_checkout_holding_the_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    halt = load_halt()
    monkeypatch.delenv("INFERENCE_HALT", raising=False)

    assert halt.default_repo_root() == REPO_ROOT
    assert halt.halt_file() == REPO_ROOT / ".agents" / "INFERENCE-HALT"
    assert halt.halt_file(None) == halt.halt_file()
    assert halt.HALT_ENV == "INFERENCE_HALT"
    assert halt.is_halted() is halt.halt_file().exists()


def test_cli_status_exit_codes(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    halt = load_halt()
    monkeypatch.delenv("INFERENCE_HALT", raising=False)

    assert halt.main(["--status", "--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "SUCCESS:inference-halt clear\n"

    assert halt.main(["--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "SUCCESS:inference-halt clear\n"

    monkeypatch.setenv("INFERENCE_HALT", "yes")
    assert halt.main(["--status", "--repo-root", str(tmp_path)]) == 1
    assert capsys.readouterr().out == "HALTED:inference env INFERENCE_HALT=yes\n"


def test_cli_set_and_clear_are_the_only_writes(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    halt = load_halt()
    monkeypatch.delenv("INFERENCE_HALT", raising=False)
    path = tmp_path / ".agents" / "INFERENCE-HALT"

    assert halt.main(["--set", "probe found a leak", "--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == f"SUCCESS:inference-halt set file={path}\n"
    assert path.read_text(encoding="utf-8") == "probe found a leak\n"

    assert halt.main(["--status", "--repo-root", str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        f"HALTED:inference file {path}: probe found a leak\n"
    )

    assert halt.main(["--clear", "--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        f"SUCCESS:inference-halt cleared file={path} existed=true\n"
    )
    assert not path.exists()
    assert halt.main(["--clear", "--repo-root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == (
        f"SUCCESS:inference-halt cleared file={path} existed=false\n"
    )
    assert halt.main(["--status", "--repo-root", str(tmp_path)]) == 0


def test_cli_refuses_conflicting_actions(tmp_path: pathlib.Path) -> None:
    halt = load_halt()

    with pytest.raises(SystemExit) as excinfo:
        halt.main(["--set", "x", "--clear", "--repo-root", str(tmp_path)])

    assert excinfo.value.code == 2
    assert not (tmp_path / ".agents").exists()


def run_halt_script(
    monkeypatch: pytest.MonkeyPatch, *argv: str, environ: dict[str, str]
) -> int:
    """Execute the script as ``__main__`` and return its process exit status."""
    monkeypatch.delenv("INFERENCE_HALT", raising=False)
    for key, value in environ.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", ["inference_halt.py", *argv])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(SCRIPTS_ROOT / "inference_halt.py"), run_name="__main__")
    code = excinfo.value.code
    assert isinstance(code, int)
    return code


def test_script_entrypoint_exits_with_the_status_code(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = ["--repo-root", str(tmp_path)]

    assert run_halt_script(monkeypatch, "--status", *root, environ={}) == 0
    assert capsys.readouterr().out == "SUCCESS:inference-halt clear\n"

    halted = run_halt_script(
        monkeypatch, "--status", *root, environ={"INFERENCE_HALT": "true"}
    )
    assert halted == 1
    assert capsys.readouterr().out == "HALTED:inference env INFERENCE_HALT=true\n"
