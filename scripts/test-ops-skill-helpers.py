#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_python(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_inspect_codex_topology(tmpdir: Path) -> None:
    home = tmpdir / "home"
    sessions = home / ".codex" / "sessions" / "a"
    sessions.mkdir(parents=True)
    (home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
    (home / ".codex" / "config.toml").write_text("[example]\n", encoding="utf-8")
    (home / ".codex" / "state_5.sqlite").write_text("", encoding="utf-8")
    (sessions / "rollout-sample.jsonl").write_text('{"id":1}\n', encoding="utf-8")

    stdout = run_python(
        "skills/codex-runtime-recovery/scripts/inspect_codex_topology.py",
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
        "skills/codex-session-reunion/scripts/session_inventory.py",
        "--json",
        str(tmpdir / "rootA"),
        str(tmpdir / "rootB"),
    )
    report = json.loads(stdout)
    assert report["total_files"] == 2
    assert report["duplicate_groups"] == 1
    assert report["invalid_files"] == 1


def test_copy_strategy(tmpdir: Path) -> None:
    archive_target = tmpdir / "bundle.tar"
    tmpdir.mkdir(parents=True, exist_ok=True)
    stdout = run_python(
        "skills/long-copy-orchestrator/scripts/copy_strategy.py",
        "recommend",
        "--source",
        r"C:\src",
        "--target",
        str(archive_target),
    )
    recommendation = json.loads(stdout)
    assert recommendation["mechanism"] == "tar"

    watch_target = tmpdir / "watch.bin"
    watch_target.write_text("12345\n", encoding="utf-8")
    stdout = run_python(
        "skills/long-copy-orchestrator/scripts/copy_strategy.py",
        "watch-file",
        str(watch_target),
        "--interval",
        "0.01",
        "--samples",
        "2",
    )
    lines = [line for line in stdout.splitlines() if line.strip()]
    json_start = next(index for index, line in enumerate(lines) if line.startswith("{"))
    report = json.loads("\n".join(lines[json_start:]))
    assert report["path"].endswith("watch.bin")
    assert "bytes_per_second" in report


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        tmpdir = Path(temp_dir)
        test_inspect_codex_topology(tmpdir / "topology")
        test_session_inventory(tmpdir / "inventory")
        test_copy_strategy(tmpdir / "copy")

    print("All ops skill helper smoke tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
