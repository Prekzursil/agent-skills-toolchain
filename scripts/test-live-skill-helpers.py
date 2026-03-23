#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = REPO_ROOT / "scripts" / "fixtures" / "skill-tests"
SKILLS_ROOT = REPO_ROOT / ".agents" / "skills" if (REPO_ROOT / ".agents" / "skills").exists() else REPO_ROOT / "skills"


def skill_path(*parts: str) -> str:
    return str(SKILLS_ROOT.joinpath(*parts).relative_to(REPO_ROOT))


def run_command(*args: str) -> str:
    result = subprocess.run(
        list(args),
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def run_python(*args: str) -> str:
    return run_command(sys.executable, *args)


def extract_trailing_json(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.strip()]
    json_start = next(index for index, line in enumerate(lines) if line.startswith("{"))
    return json.loads("\n".join(lines[json_start:]))


def test_inspect_codex_topology(tmpdir: Path) -> None:
    home = tmpdir / "home"
    sessions = home / ".codex" / "sessions" / "a"
    sessions.mkdir(parents=True)
    (home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
    (home / ".codex" / "config.toml").write_text("[example]\n", encoding="utf-8")
    (home / ".codex" / "state_5.sqlite").write_text("", encoding="utf-8")
    (sessions / "rollout-sample.jsonl").write_text('{"id":1}\n', encoding="utf-8")

    stdout = run_python(
        skill_path("codex-runtime-recovery", "scripts", "inspect_codex_topology.py"),
        "--home",
        str(home),
        "--json",
    )
    report = json.loads(stdout)
    first_root = report["roots"][0]
    assert first_root["exists"] is True
    assert first_root["sessions"] == 1
    assert first_root["auth_json"] is True


def test_session_inventory(tmpdir: Path) -> None:
    root_a = tmpdir / "rootA" / "sessions" / "a"
    root_b = tmpdir / "rootB" / "sessions" / "b"
    root_a.mkdir(parents=True)
    root_b.mkdir(parents=True)
    (root_a / "rollout-test.jsonl").write_text('{"id":1}\n', encoding="utf-8")
    (root_b / "rollout-test.jsonl").write_text("not-json\n", encoding="utf-8")

    stdout = run_python(
        skill_path("codex-session-reunion", "scripts", "session_inventory.py"),
        "--json",
        str(tmpdir / "rootA"),
        str(tmpdir / "rootB"),
    )
    report = json.loads(stdout)
    assert report["total_files"] == 2
    assert report["duplicate_groups"] == 1
    assert report["invalid_files"] == 1


def test_copy_strategy(tmpdir: Path) -> None:
    tmpdir.mkdir(parents=True, exist_ok=True)
    archive_target = tmpdir / "bundle.tar"
    stdout = run_python(
        skill_path("long-copy-orchestrator", "scripts", "copy_strategy.py"),
        "recommend",
        "--source",
        r"C:\src",
        "--target",
        str(archive_target),
    )
    recommendation = json.loads(stdout)
    assert recommendation["mechanism"] == "tar"

    stdout = run_python(
        skill_path("long-copy-orchestrator", "scripts", "copy_strategy.py"),
        "recommend",
        "--source",
        str(tmpdir / "guest.vmdk"),
        "--target",
        r"D:\vm-target",
    )
    recommendation = json.loads(stdout)
    assert recommendation["mechanism"] == "offline-attach"

    watch_target = tmpdir / "watch.bin"
    watch_target.write_text("12345\n", encoding="utf-8")
    stdout = run_python(
        skill_path("long-copy-orchestrator", "scripts", "copy_strategy.py"),
        "watch-file",
        str(watch_target),
        "--interval",
        "0.01",
        "--samples",
        "2",
    )
    report = extract_trailing_json(stdout)
    assert report["path"].endswith("watch.bin")
    assert "bytes_per_second" in report


def test_format_codex_sessions_fixture() -> None:
    fixture = FIXTURES_ROOT / "format-codex-sessions" / "sample-session.jsonl"

    readable = run_command(
        "node",
        skill_path("format-codex-sessions", "scripts", "render_codex_session.mjs"),
        "--input",
        str(fixture),
        "--mode",
        "readable",
    )
    assert "# Codex Session Transcript" in readable
    assert "### Tool Activity" in readable
    assert "Ran exec_command: `echo hello from helper`" in readable
    assert "[AGENTS instructions attached]" in readable
    assert "Bearer [REDACTED]" in readable
    assert "[REDACTED_API_KEY]" in readable
    assert "developer prompt omitted" not in readable
    assert "Top secret developer prompt" not in readable

    audit = run_command(
        "node",
        skill_path("format-codex-sessions", "scripts", "render_codex_session.mjs"),
        "--input",
        str(fixture),
        "--mode",
        "audit",
    )
    assert "[developer prompt omitted]" in audit
    assert "### Tool Activity" in audit
    assert "Reasoning step omitted." in audit

    dialogue = run_command(
        "node",
        skill_path("format-codex-sessions", "scripts", "render_codex_session.mjs"),
        "--input",
        str(fixture),
        "--mode",
        "dialogue",
    )
    assert "### User" in dialogue
    assert "### Assistant" in dialogue
    assert "### Tool Activity" not in dialogue
    assert "[developer prompt omitted]" not in dialogue


def test_quality_zero_platform_control_plane_fixture() -> None:
    fixture = FIXTURES_ROOT / "quality-zero-platform-control-plane"

    good = run_python(
        skill_path("quality-zero-platform-control-plane", "scripts", "audit_quality_zero_platform.py"),
        "--repo",
        "Prekzursil/good-repo",
        "--fixture-dir",
        str(fixture),
        "--format",
        "json",
    )
    good_report = json.loads(good)
    assert good_report["status"] == "success"
    assert good_report["enrolled"] is True
    assert good_report["ruleset_present"] is True
    assert good_report["drift_categories"] == []

    drift = run_python(
        skill_path("quality-zero-platform-control-plane", "scripts", "audit_quality_zero_platform.py"),
        "--repo",
        "Prekzursil/drift-repo",
        "--fixture-dir",
        str(fixture),
        "--format",
        "json",
    )
    drift_report = json.loads(drift)
    assert drift_report["status"] == "partial"
    assert drift_report["enrolled"] is True
    assert "missing_wrappers" in drift_report["drift_categories"]
    assert "missing_ruleset" in drift_report["drift_categories"]
    assert "failing_runs" in drift_report["drift_categories"]

    markdown = run_python(
        skill_path("quality-zero-platform-control-plane", "scripts", "audit_quality_zero_platform.py"),
        "--repo",
        "Prekzursil/drift-repo",
        "--fixture-dir",
        str(fixture),
        "--format",
        "md",
    )
    assert "# Quality Zero Platform Audit" in markdown
    assert "Status: `partial`" in markdown
    assert "`missing_ruleset`" in markdown


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        tmpdir = Path(temp_dir)
        test_inspect_codex_topology(tmpdir / "topology")
        test_session_inventory(tmpdir / "inventory")
        test_copy_strategy(tmpdir / "copy")
    test_format_codex_sessions_fixture()
    test_quality_zero_platform_control_plane_fixture()

    print("All live skill helper smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
