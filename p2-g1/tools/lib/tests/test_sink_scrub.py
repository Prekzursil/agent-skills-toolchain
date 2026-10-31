#!/usr/bin/env python3
"""Library tests for the sink-level scrubber (TST-0209 rebuild, shard17-w4).

The dead prior builder's receipt named this file as a PASSing test row but left
no file on disk; this rebuild makes the row real. Run: python3 -B this file.
"""
from __future__ import annotations
import io
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LIB))

import sink_scrub  # noqa: E402
from secret_shapes import iter_shapes  # noqa: E402


def test_scrub_removes_every_shape_infix():
    for s in iter_shapes():
        out = sink_scrub.scrub(f"boom {s.secret} tail")
        assert s.infix not in out, f"infix survived: {s.infix}"
        assert sink_scrub.REDACTED in out


def test_scrub_plain_text_untouched():
    assert sink_scrub.scrub("nothing secret here") == "nothing secret here"


def test_capture_sink_routes_and_restores():
    shapes = iter_shapes()
    buf, _ = sink_scrub.capture_sink()
    try:
        sink_scrub._emit(f"err {shapes[0].secret}")
        body = buf.getvalue()
        assert shapes[0].infix not in body
        assert sink_scrub.REDACTED in body
    finally:
        sink_scrub.reset_sink()
    assert sys.stderr is not buf  # restored


def test_mutant_raw_write_leaks():
    shapes = iter_shapes()
    buf = io.StringIO()
    sink_scrub.mutant_raw_write(buf, f"err {shapes[1].secret}")
    assert shapes[1].infix in buf.getvalue()  # bypassing the sink leaks


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"SUCCESS:test_sink_scrub {len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
