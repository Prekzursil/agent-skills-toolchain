#!/usr/bin/env python3
"""Rendered-column measurement for TST-0246.

Two independent meters:

  * libc wcwidth/wcswidth — the POSIX table Linux terminals (including
    tmux) consult.
  * a live tmux pane's ``#{cursor_x}`` after a literal send of the line
    — a real terminal emulator's cursor, not a Python len().

Windows Terminal disagrees with libc on U+26A0 (ambiguous/emoji). The
WT model treats the scanner's breaker class as width 2 so the overlap
is visible even on this Linux box where tmux/wcwidth report 1.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import subprocess
import tempfile
from typing import Any

from scan import classify_char

_LIBC = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
_LIBC.wcwidth.argtypes = [ctypes.c_wchar]
_LIBC.wcwidth.restype = ctypes.c_int
_LIBC.wcswidth.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t]
_LIBC.wcswidth.restype = ctypes.c_int


def libc_wcwidth(ch: str) -> int:
    return int(_LIBC.wcwidth(ch[0]))


def libc_wcswidth(text: str) -> int:
    if not text:
        return 0
    return int(_LIBC.wcswidth(text, len(text)))


def wt_model_width(ch: str, nxt: str | None = None) -> int:
    """Windows Terminal overlap model: breaker class occupies 2 columns."""
    w = libc_wcwidth(ch)
    if w < 0:
        return 0
    if classify_char(ch, nxt):
        return 2
    return w


def wt_model_columns(text: str) -> int:
    total = 0
    for i, ch in enumerate(text):
        nxt = text[i + 1] if i + 1 < len(text) else None
        total += wt_model_width(ch, nxt)
    return total


def tmux_cursor_x(text: str, *, cols: int = 200) -> dict[str, Any]:
    """Write ``text`` (no newline) into a fresh tmux pane; read cursor_x."""
    if "\n" in text or "\r" in text:
        raise ValueError("tmux meter takes a single line")
    if len(text) >= cols:
        raise ValueError(f"line length {len(text)} does not fit cols={cols}")
    sock_dir = tempfile.mkdtemp(prefix="tst0246-tmux-")
    sock = os.path.join(sock_dir, "sock")
    name = "t0246"
    env = os.environ.copy()
    env.pop("TMUX", None)
    try:
        subprocess.run(
            [
                "tmux",
                "-S",
                sock,
                "new-session",
                "-d",
                "-x",
                str(cols),
                "-y",
                "8",
                "-s",
                name,
            ],
            check=True,
            capture_output=True,
            env=env,
        )
        if text:
            # `--` is required: a HUD rule of hyphens otherwise looks like flags.
            subprocess.run(
                ["tmux", "-S", sock, "send-keys", "-t", name, "-l", "--", text],
                check=True,
                capture_output=True,
                env=env,
            )
        out = subprocess.check_output(
            [
                "tmux",
                "-S",
                sock,
                "display-message",
                "-p",
                "-t",
                name,
                "#{cursor_x}",
            ],
            env=env,
        )
        cursor = int(out.decode("utf-8").strip())
        return {
            "ok": True,
            "method": "tmux-#{cursor_x}",
            "cursor_x": cursor,
            "cols": cols,
        }
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        return {
            "ok": False,
            "method": "tmux-#{cursor_x}",
            "cursor_x": None,
            "error": f"{type(exc).__name__}: {exc}",
            "cols": cols,
        }
    finally:
        subprocess.run(
            ["tmux", "-S", sock, "kill-server"],
            capture_output=True,
            env=env,
        )
        try:
            os.unlink(sock)
        except OSError:
            pass
        try:
            os.rmdir(sock_dir)
        except OSError:
            pass


def measure_line(text: str) -> dict[str, Any]:
    tmux = tmux_cursor_x(text)
    wc = libc_wcswidth(text)
    wt = wt_model_columns(text)
    return {
        "text": text,
        "codepoints": len(text),
        "libc_wcswidth": wc,
        "tmux": tmux,
        "tmux_cursor_x": tmux.get("cursor_x"),
        "wt_model_columns": wt,
    }
