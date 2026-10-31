"""IMP-0056 tests: the secret body never reaches the log; the record does."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.jsonl_log import JsonlLogger  # noqa: E402

SECRET = "ghp_" + "AbCdEf1234567890ABCDEF"


def _read_all(log: Path) -> bytes:
    blob = b""
    for seg in sorted(log.parent.glob(log.name + "*")):
        blob += seg.read_bytes()
    return blob


def test_secret_body_never_written(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    lg = JsonlLogger(log, "IMP-0056", max_bytes=4096, max_files=3)
    rec = lg.write("TOKEN-HANDLED", token=SECRET, note="used " + SECRET + " once")
    assert rec["fields"]["token"] == "[REDACTED]"
    blob = _read_all(log)
    assert SECRET.encode() not in blob, "raw secret body reached the log"
    assert blob.count(b"[REDACTED]") >= 2
    # the record that referenced the secret is still present
    assert b"TOKEN-HANDLED" in blob
    assert b"IMP-0056" in blob


def test_negative_control_disabled_filter_leaks_secret(tmp_path: Path) -> None:
    log = tmp_path / "leak.log"
    lg = JsonlLogger(log, "IMP-0056", redact=False, max_bytes=4096, max_files=3)
    lg.write("TOKEN-HANDLED", token=SECRET)
    blob = _read_all(log)
    assert SECRET.encode() in blob, "grep detector cannot work if the control never leaks"
