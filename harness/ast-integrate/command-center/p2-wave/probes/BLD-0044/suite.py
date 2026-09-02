"""Planted control tests. Outcomes are environment-sensitive except test_hermetic.

These are not a substitute for an off-tree product suite. They are the both-states
detector corpus: each hidden-input class has one test that MUST flip, and one
hermetic test that MUST NOT.
"""
from __future__ import annotations

import os
import random
import time
from pathlib import Path

from common import SUITE_MARKER, deliberate_fetch


def test_hermetic() -> None:
    """Genuinely hermetic: 2+2. Must PASS identically in every cell."""
    if 2 + 2 != 4:
        raise AssertionError("arithmetic broke")


def test_order_write() -> None:
    scratch = Path(os.environ["BLD0044_SCRATCH"])
    (scratch / "token").write_text("written", encoding="utf-8")


def test_order_read() -> None:
    scratch = Path(os.environ["BLD0044_SCRATCH"])
    token = scratch / "token"
    if not token.is_file():
        raise AssertionError("order-hidden-input: reader ran before writer")
    if token.read_text(encoding="utf-8") != "written":
        raise AssertionError("token mismatch")


def test_tz_utc_offset() -> None:
    """Hidden TZ: passes only when local offset is UTC."""
    off = time.strftime("%z")
    if off not in ("+0000", "+00:00"):
        raise AssertionError(f"tz-hidden-input: offset={off} (want UTC)")


def test_cwd_marker() -> None:
    """Hidden cwd: looks for SUITE_MARKER as a relative path."""
    if not Path("SUITE_MARKER").is_file():
        raise AssertionError(f"cwd-hidden-input: no SUITE_MARKER in {os.getcwd()}")
    if Path("SUITE_MARKER").read_text(encoding="utf-8").strip() != "bld-0044-suite-home":
        raise AssertionError("cwd marker contents wrong")
    # Absolute path still exists; the test did not use it — that is the hidden input.
    if not SUITE_MARKER.is_file():
        raise AssertionError("suite marker missing on disk")


def test_cache_hit() -> None:
    cache = Path(os.environ["BLD0044_CACHE"])
    token = cache / "warm-token"
    if not token.is_file():
        raise AssertionError("cache-hidden-input: cold cache, no warm-token")
    if token.read_text(encoding="utf-8") != "warm":
        raise AssertionError("warm-token contents wrong")


def test_prng_draw() -> None:
    """Hidden PRNG: passes only for seeds that draw 7 from randint(0, 20)."""
    draw = random.randint(0, 20)
    if draw != 7:
        raise AssertionError(f"prng-hidden-input: draw={draw} want=7")


def test_undeclared_fetch() -> None:
    """This test never downloads. (The comment is the lie; the body opens a socket.)"""
    deliberate_fetch()
