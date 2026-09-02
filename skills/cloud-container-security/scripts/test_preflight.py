"""Offline tests for preflight.py — fakes only, no network, no subprocess."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import preflight  # noqa: E402


def fake_which(mapping: dict[str, str]):
    """Build a shutil.which stand-in from a {tool: path} mapping."""

    def _which(name: str) -> str | None:
        return mapping.get(name)

    return _which


def test_check_tools_reports_present_and_absent():
    which = fake_which({"trivy": "/usr/bin/trivy", "syft": "/usr/local/bin/syft"})
    results = preflight.check_tools(["trivy", "syft", "prowler"], which=which)
    assert results == {
        "trivy": "/usr/bin/trivy",
        "syft": "/usr/local/bin/syft",
        "prowler": None,
    }


def test_check_tools_defaults_to_full_matrix():
    results = preflight.check_tools(which=fake_which({}))
    assert set(results) == set(preflight.TOOLS)
    assert all(path is None for path in results.values())
    assert len(results) == 7 + 1  # the seven tools plus Steampipe's Powerpipe


def test_format_report_marks_present_and_absent():
    report = preflight.format_report({"trivy": "/usr/bin/trivy", "prowler": None})
    assert "[ok] trivy" in report
    assert "[--] prowler" in report
    assert "not on PATH" in report
    assert "1/2 tools present" in report


def test_main_is_fail_open_and_uses_injected_which(capsys):
    which = fake_which({"cloudfox": "/opt/cloudfox"})
    rc = preflight.main(["--tools", "cloudfox", "trivy"], which=which)
    assert rc == 0
    out = capsys.readouterr().out
    assert "/opt/cloudfox" in out
    assert "[--] trivy" in out


def test_main_all_absent_still_exits_zero(capsys):
    rc = preflight.main([], which=fake_which({}))
    assert rc == 0
    assert "0/8 tools present" in capsys.readouterr().out


def test_preflight_never_uses_network_or_subprocess(monkeypatch):
    import socket
    import subprocess

    def boom(*args, **kwargs):
        raise AssertionError("preflight must not use network or subprocess")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    assert preflight.main(["--tools", "trivy"], which=fake_which({})) == 0
