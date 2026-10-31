"""Windows CreateProcess 32767-char guard with prompt-file switch (TST-0063)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

WINDOWS_CREATEPROCESS_CHAR_CEILING = 32767
WINERROR_FILENAME_EXCED_RANGE = 206
INLINE_PAYLOAD_THAT_DIED = "inline-payload-that-died"
SWITCH_EVENT = "switched-to-prompt-file"


def windows_cmdline_chars(argv: Sequence[str]) -> int:
    # Approximate Windows CommandLineToArgvW quoting.
    total = 0
    parts = []
    for i, arg in enumerate(argv):
        if i:
            parts.append(" ")
            total += 1
        need = any(ch in arg for ch in ' \t"') or arg == ""
        if not need:
            parts.append(arg)
            total += len(arg)
            continue
        escaped = arg.replace("\\", "\\\\").replace('"', '\\"')
        quoted = f'"{escaped}"'
        parts.append(quoted)
        total += len(quoted)
    return total


def payload_digest(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def pad_payload_for_inline_chars(vendor: Sequence[str], extra: Sequence[str], target: int) -> str:
    extra = list(extra)
    n = max(0, target)
    payload = "P" * n
    for _ in range(8):
        got = windows_cmdline_chars(list(vendor) + ["--prompt", payload] + extra)
        delta = target - got
        if delta == 0:
            return payload
        n = max(0, n + delta)
        payload = "P" * n
    got = windows_cmdline_chars(list(vendor) + ["--prompt", payload] + extra)
    if got != target:
        raise RuntimeError(f"pad missed target={target} got={got}")
    return payload


@dataclass
class Marshal:
    transport: str
    switched: bool
    inline_chars: int
    would_raise_206_if_inline: bool

    @property
    def windows_chars(self) -> int:
        return self.inline_chars


@dataclass
class SpawnResult:
    exit_code: int
    winerror: int | None
    marshal: Marshal
    child: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "winerror": self.winerror,
            "transport": self.marshal.transport,
            "switched": self.marshal.switched,
            "inline_chars": self.marshal.inline_chars,
            "child": self.child,
        }


def spawn_guarded(
    vendor: Sequence[str],
    payload: str,
    workdir: Path | None = None,
    **kwargs: Any,
) -> SpawnResult:
    argv_inline = list(vendor) + ["--prompt", payload]
    chars = windows_cmdline_chars(argv_inline)
    over = chars >= WINDOWS_CREATEPROCESS_CHAR_CEILING
    workdir = Path(workdir or ".")
    workdir.mkdir(parents=True, exist_ok=True)
    if over:
        prompt_file = workdir / "prompt.txt"
        prompt_file.write_text(payload, encoding="utf-8")
        argv = list(vendor) + ["--prompt-file", str(prompt_file)]
        marshal = Marshal(
            transport="prompt-file",
            switched=True,
            inline_chars=chars,
            would_raise_206_if_inline=True,
        )
    else:
        argv = argv_inline
        marshal = Marshal(
            transport="inline",
            switched=False,
            inline_chars=chars,
            would_raise_206_if_inline=False,
        )
    p = subprocess.run(
        argv,
        cwd=str(workdir),
        capture_output=True,
        text=True,
    )
    child = None
    text = (p.stdout or "").strip()
    if text:
        try:
            child = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            try:
                child = json.loads(text)
            except json.JSONDecodeError:
                child = {"ok": p.returncode == 0, "raw": text[:200]}
    return SpawnResult(exit_code=p.returncode, winerror=None, marshal=marshal, child=child)


def naive_linux_spawn(argv: Sequence[str]) -> dict[str, Any]:
    try:
        p = subprocess.run(list(argv), capture_output=True, text=True, timeout=10)
        return {"ok": p.returncode == 0, "returncode": p.returncode}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}
