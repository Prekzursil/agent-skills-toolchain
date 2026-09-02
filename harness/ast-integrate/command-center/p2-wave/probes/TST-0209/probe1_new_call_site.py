#!/usr/bin/env python3
"""Probe 1: detector control — new unscrubbed call site still redacted at the sink.

Both-states: the same payload written while bypassing the sink MUST leak,
otherwise a green here would not prove the detector is live.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "tools" / "lib"
sys.path.insert(0, str(LIB))

from observability import emit_telemetry, log_error, log_exception  # noqa: E402
from secret_shapes import iter_shapes  # noqa: E402
from sink_scrub import (  # noqa: E402
    REDACTED,
    capture_sink,
    mutant_raw_write,
    reset_sink,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0209-probe1 {msg}")
    return 1


def new_unscrubbed_call_site(message: str) -> str:
    """A newly added logging call site. It does not redact."""
    return log_error(message)


def main() -> int:
    shapes = iter_shapes()
    log_shape = shapes[0]
    exc_shape = shapes[11]  # pem family appears later; use jwt-ish / another family
    tel_shape = shapes[13]

    sink, buf = capture_sink()
    try:
        logged = new_unscrubbed_call_site(log_shape.exception_message())
        try:
            raise RuntimeError(exc_shape.exception_message())
        except RuntimeError as exc:
            traced = log_exception(exc)
        telem = emit_telemetry("probe1-new-site", {"token": tel_shape.secret})
        captured = buf.getvalue()
    finally:
        reset_sink()

    checks = [
        ("log", log_shape, logged),
        ("exception", exc_shape, traced),
        ("telemetry", tel_shape, telem),
    ]
    for name, shape, out in checks:
        if shape.infix in out:
            return fail(f"{name} channel leaked family={shape.family} index={shape.index}")
        if REDACTED not in out:
            return fail(f"{name} channel missing redaction marker family={shape.family}")
        print(f"new_site_{name} redacted=True family={shape.family} marker={REDACTED}")

    if any(s.infix in captured for s in (log_shape, exc_shape, tel_shape)):
        return fail("sink stream retained an infix")
    print("sink_stream_clean=True")

    bypass = io.StringIO()
    mutant_raw_write(bypass, log_shape.exception_message())
    leaked = log_shape.infix in bypass.getvalue()
    print(f"bypass_sink_leaks={leaked}")
    if not leaked:
        return fail("bypass mutant silent — detector would be vacuous")

    # Source of THIS probe must not call scrub (it is the new call site).
    src = Path(__file__).read_text(encoding="utf-8")
    body = src.split("def new_unscrubbed_call_site", 1)[1].split("\ndef main", 1)[0]
    if "scrub(" in body:
        return fail("new call site function redacts locally")
    print("new_call_site_source_has_no_scrub=True")

    summary = {
        "probe": "probe1-new-unscrubbed-call-site",
        "unit_id": "TST-0209",
        "pass": True,
        "channels": ["log", "exception", "telemetry"],
        "bypass_sink_leaks": True,
        "new_call_site_redacts_locally": False,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0209-probe1 new unscrubbed call site redacted; bypass leaks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
