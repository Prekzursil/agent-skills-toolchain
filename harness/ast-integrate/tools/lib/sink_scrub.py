"""Sink-level secret scrubbing (the only production redaction choke point)."""
from __future__ import annotations

import io
import sys
from typing import TextIO

from secret_shapes import iter_shapes

REDACTED = "[REDACTED]"
_SINK: TextIO | None = None
_PREV: TextIO | None = None


def _infixes() -> tuple[str, ...]:
    return tuple(s.infix for s in iter_shapes())


def scrub(text: str) -> str:
    out = str(text)
    for infix in _infixes():
        if infix in out:
            out = out.replace(infix, REDACTED)
    return out


def capture_sink() -> tuple[TextIO, io.StringIO]:
    global _SINK, _PREV
    buf = io.StringIO()
    _PREV = sys.stderr
    sys.stderr = buf
    _SINK = buf
    return buf, buf


def reset_sink() -> None:
    global _SINK, _PREV
    if _PREV is not None:
        sys.stderr = _PREV
    _SINK = None
    _PREV = None


def _emit(text: str) -> str:
    cleaned = scrub(text)
    sink = _SINK if _SINK is not None else sys.stderr
    sink.write(cleaned)
    return cleaned


def mutant_raw_write(buf: TextIO, text: str) -> None:
    buf.write(str(text))


def mutant_call_site_redact_then_write(buf: TextIO, text: str) -> None:
    buf.write(scrub(text))
