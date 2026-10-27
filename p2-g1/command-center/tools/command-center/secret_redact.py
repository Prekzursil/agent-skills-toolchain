"""Redact canaries and named env values before writing artifacts."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Iterable


def scrub_env_values(text: str, env_names: Iterable[str] | None = None) -> str:
    names = list(env_names or [])
    out = text
    for name in names:
        val = os.environ.get(name)
        if val:
            out = out.replace(val, f"[REDACTED:{name}]")
    return out


def redact_text(text: str, extra_needles: Iterable[str] | None = None, env_names: Iterable[str] | None = None) -> str:
    out = scrub_env_values(text, env_names)
    for needle in extra_needles or []:
        if needle:
            out = out.replace(str(needle), "[REDACTED]")
    out = re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", r"\1=[REDACTED]", out)
    return out


def safe_write(
    path: str | Path,
    body: str,
    extra_needles: Iterable[str] | None = None,
    env_names: Iterable[str] | None = None,
    **kwargs: Any,
) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    redacted = redact_text(body, extra_needles=extra_needles, env_names=env_names)
    if not redacted.endswith("\n"):
        redacted += "\n"
    dest.write_text(redacted, encoding="utf-8")
