#!/usr/bin/env python3
"""Tests for the degrade-loudly channel (IMP-0054).

The proof of every claim is the disk after the writer process has exited, not
an in-process return value.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parent
sys.path.insert(0, str(PLUGIN))

import degrade_loudly as dl  # noqa: E402

MOD = PLUGIN / "degrade_loudly.py"


def _run(args: list[str], sink: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env[dl.ENV_SINK] = str(sink)
    return subprocess.run(
        [sys.executable, "-B", str(MOD), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def test_ignored_warning_still_persists() -> None:
    with tempfile.TemporaryDirectory() as td:
        sink = Path(td) / "sink"
        # Writer process discards the handle and exits.
        proc = _run(["discard-warn", "--sink", str(sink), "--code", "T.IGNORED", "--message", "dropped"], sink)
        assert proc.returncode == 0, proc.stderr
        assert "discarded-return=true" in proc.stdout
        assert "1 warning(s) recorded" in proc.stderr, proc.stderr  # exit surface printed
        recs = [json.loads(l) for l in (sink / dl.ACTIVE_NAME).read_text(encoding="utf-8").splitlines()]
        assert any(r["code"] == "T.IGNORED" and r["message"] == "dropped" for r in recs)
        assert all(dl.validate_record(r) == [] for r in recs), [dl.validate_record(r) for r in recs]
        surface = json.loads((sink / dl.EXIT_SURFACE_NAME).read_text(encoding="utf-8"))
        assert surface["count"] == 1 and surface["codes"] == ["T.IGNORED"]
        # A later process surfaces it.
        health = _run(["health", "--sink", str(sink)], sink)
        report = json.loads(health.stdout.strip().splitlines()[-1])
        assert report["verdict"] == dl.WARNINGS_PRESENT and report["count"] == 1
        assert report["exit_surface"]["count"] == 1
        # In-process: the message is truncated at the bound, the record still lands.
        handle = dl.Sink(dl.SinkConfig(directory=sink)).warn("T.LONG", "x" * 5000)
        assert handle.record.truncated and len(handle.record.message) == dl.MESSAGE_TRUNCATE_AT
        assert dl.Sink(dl.SinkConfig(directory=sink)).health_check()["count"] == 2


def test_empty_sink_health_is_explicit() -> None:
    with tempfile.TemporaryDirectory() as td:
        empty = Path(td) / "empty"
        empty.mkdir()
        report = dl.Sink(dl.SinkConfig(directory=empty)).health_check()
        assert report["verdict"] == dl.NO_WARNINGS
        assert report["empty_sink"] is True and report["empty_sink_declared"] is True
        assert "no warnings" in report["explicit"].lower()
        assert report["warnings_present"] is False and report["records"] == []
        # A sink directory that does not exist yet is also explicit-empty, not a crash.
        missing = dl.Sink(dl.SinkConfig(directory=Path(td) / "never")).health_check()
        assert missing["verdict"] == dl.NO_WARNINGS and missing["sink_exists"] is False
        # Warned and empty reports must differ (silence is not the healthy signal).
        warned = Path(td) / "warned"
        dl.Sink(dl.SinkConfig(directory=warned)).warn("T.ONE", "one")
        w = dl.Sink(dl.SinkConfig(directory=warned)).health_check()
        assert w["verdict"] == dl.WARNINGS_PRESENT and w["empty_sink_declared"] is False
        assert json.dumps(w, sort_keys=True) != json.dumps(report, sort_keys=True)


def test_sink_rotates_and_cannot_grow_without_limit() -> None:
    with tempfile.TemporaryDirectory() as td:
        bounded = Path(td) / "bounded"
        cfg = dl.SinkConfig(directory=bounded, max_file_bytes=400, max_files=3, hard_ceiling_bytes=900)
        sink = dl.Sink(cfg)
        rotated_once = False
        for i in range(60):
            handle = sink.warn("T.FLOOD", ("n" * 80) + f"-{i}")
            rotated_once = rotated_once or handle.rotated
            assert sink.total_bytes() <= 900, sink.total_bytes()
            assert len(list(bounded.glob(dl.ACTIVE_NAME + "*"))) <= 3
        assert rotated_once
        assert (bounded / (dl.ACTIVE_NAME + ".1")).is_file()
        # Newest records survive rotation; the oldest were dropped.
        codes_msgs = [r["message"] for r in sink.records()]
        assert codes_msgs[-1].endswith("-59") and not any(m.endswith("-0") for m in codes_msgs)
        assert sink.health_check()["bounds"]["within_ceiling"] is True
        # Negative control: rotate=False exceeds the ceiling.
        unbounded = Path(td) / "unbounded"
        loose = dl.Sink(dl.SinkConfig(directory=unbounded, max_file_bytes=400, max_files=3, hard_ceiling_bytes=900, rotate=False))
        for i in range(60):
            loose.warn("T.FLOOD", ("n" * 80) + f"-{i}")
        assert loose.total_bytes() > 900
        assert loose.health_check()["bounds"]["within_ceiling"] is False
        # Production defaults sit below the 774 KiB pathology.
        assert dl.DEFAULT_HARD_CEILING_BYTES < dl.PATHOLOGY_REFERENCE_BYTES
        try:
            dl.SinkConfig(directory=bounded, max_files=0)
        except ValueError:
            pass
        else:
            raise AssertionError("max_files=0 accepted")


def test_corrupt_line_is_surfaced_not_swallowed() -> None:
    with tempfile.TemporaryDirectory() as td:
        sink = Path(td) / "s"
        sink.mkdir()
        (sink / dl.ACTIVE_NAME).write_text('{"code": "OK", "message": "m"}\nnot json\n', encoding="utf-8")
        report = dl.Sink(dl.SinkConfig(directory=sink)).health_check()
        assert report["verdict"] == dl.WARNINGS_PRESENT
        assert any(r.get("corrupt") for r in report["records"])


TESTS = [
    test_ignored_warning_still_persists,
    test_empty_sink_health_is_explicit,
    test_sink_rotates_and_cannot_grow_without_limit,
    test_corrupt_line_is_surfaced_not_swallowed,
]


def main() -> int:
    for test in TESTS:
        test()
        print(f"ok {test.__name__}")
    print(f"SUCCESS:IMP-0054-tests {len(TESTS)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
