"""IMP-0056 tests: rotation bounds hold by size AND count."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.jsonl_log import JsonlLogger  # noqa: E402


def test_size_and_count_bounds_hold(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    lg = JsonlLogger(log, "IMP-0056", max_bytes=512, max_files=3)
    for i in range(120):
        lg.write("LOAD", i=i, filler="x" * 24)
    segments = sorted(log.parent.glob("events.log*"))
    assert 1 <= len(segments) <= 3, [s.name for s in segments]
    for seg in segments:
        assert seg.stat().st_size <= 512, (seg.name, seg.stat().st_size)
    total = sum(s.stat().st_size for s in segments)
    assert total <= 512 * 3 + 512, total
    # every surviving line parses
    for seg in segments:
        for line in seg.read_text(encoding="utf-8").splitlines():
            if line.strip():
                json.loads(line)


def test_newest_record_survives_rotation(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    lg = JsonlLogger(log, "IMP-0056", max_bytes=256, max_files=2)
    marker = "imp0056-final-marker"
    for i in range(40):
        lg.write("LOAD", i=i, filler="y" * 16)
    lg.write("FINAL", marker=marker)
    blob = b"".join(s.read_bytes() for s in sorted(log.parent.glob("events.log*")))
    assert marker.encode() in blob
