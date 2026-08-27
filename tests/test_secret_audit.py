from __future__ import annotations

import importlib.util
import pathlib
import sys


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "audit_secret_artifacts.py"
SPEC = importlib.util.spec_from_file_location("audit_secret_artifacts", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def test_reference_only_config_is_clean(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "safe.json"
    path.write_text(
        '{"Authorization": "Bearer ${GITHUB_MCP_PAT}", "token": "env:APIFY_TOKEN", '
        '"bearer_token_env_var": "GITHUB_MCP_PAT"}',
        encoding="utf-8",
    )

    result = audit.audit([tmp_path], ["GITHUB_MCP_PAT", "APIFY_TOKEN"], 1024)

    assert result["findings"] == []


def test_literal_environment_value_is_reported_without_value(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    path = tmp_path / "unsafe.json"
    secret = "fixture-sensitive-value-123456789"
    monkeypatch.setenv("EXAMPLE_API_TOKEN", secret)
    path.write_text('{"EXAMPLE_API_TOKEN": "' + secret + '"}', encoding="utf-8")

    result = audit.audit([tmp_path], ["EXAMPLE_API_TOKEN"], 1024)

    assert result["findings"]
    rendered = str(result)
    assert secret not in rendered
    assert "EXAMPLE_API_TOKEN" in rendered


def test_strong_token_pattern_and_private_key_header_are_detected(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "unsafe.log"
    path.write_text(
        "github_pat_" + "A" * 30 + "\n-----BEGIN PRIVATE KEY-----\n",
        encoding="utf-8",
    )

    findings = audit.scan_file(path, {})

    assert {item.name for item in findings} == {"github", "private-key"}


def test_high_entropy_generic_credential_literal_is_detected(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "unsafe.toml"
    path.write_text(
        'BROWSERSTACK_ACCESS_KEY = "aB19xY27mN35qR43tV51zC69"\n',
        encoding="utf-8",
    )

    findings = audit.scan_file(path, {})

    assert [(item.detector, item.name) for item in findings] == [
        ("credential-literal", "BROWSERSTACK_ACCESS_KEY")
    ]


def test_binary_and_large_files_are_bounded(tmp_path: pathlib.Path) -> None:
    (tmp_path / "binary.log").write_bytes(b"abc\x00github_pat_" + b"A" * 40)
    (tmp_path / "large.log").write_text("x" * 2048, encoding="utf-8")

    files = list(audit.iter_files([tmp_path], max_bytes=1024))

    assert [path.name for path in files] == ["binary.log"]
    assert audit.scan_file(files[0], {}) == []
