#!/usr/bin/env python3
"""String-harvest env vars, flags, and subcommands from the shipped client."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

WRAPPER_ENV_RE = re.compile(
    r"\$\{([A-Z][A-Z0-9_]{2,})(?::-)?\}|\$([A-Z][A-Z0-9_]{2,})\b"
)
PROCESS_ENV_RE = re.compile(r"process\.env(?:\.([A-Z][A-Z0-9_]{2,})|\[['\"]([A-Z][A-Z0-9_]{2,})['\"]\])")
QUOTED_ENV_RE = re.compile(r"['\"]([A-Z][A-Z0-9_]{3,})['\"]")
FLAG_RE = re.compile(r"(--[a-z][a-z0-9-]{2,})")
KEEP_ENV_PREFIX = ("CURSOR_", "AGENT_", "CLAUDE_", "ANTHROPIC_", "NO_OPEN_", "NODE_COMPILE", "NODE_EXTRA", "NODE_USE_ENV")


def wrapper_env_names(text: str) -> list[str]:
    names: set[str] = set()
    for a, b in WRAPPER_ENV_RE.findall(text):
        names.add(a or b)
    return sorted(names)


def js_env_names(blob: str) -> list[str]:
    names: set[str] = set()
    for a, b in PROCESS_ENV_RE.findall(blob):
        names.add(a or b)
    for name in QUOTED_ENV_RE.findall(blob):
        if name.startswith(KEEP_ENV_PREFIX) or name in {"NO_OPEN_BROWSER", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"}:
            names.add(name)
    return sorted(names)


def js_flags(blob: str) -> list[str]:
    found = set(FLAG_RE.findall(blob))
    # Drop CSS-like and generic noise.
    out = []
    for f in sorted(found):
        if f.count("-") > 6:
            continue
        if len(f) > 40:
            continue
        out.append(f)
    return out


def load_published() -> dict:
    path = HERE / "fixtures" / "published_tokens.json"
    return json.loads(path.read_text(encoding="utf-8"))


def parse_help_surface(help_text: str) -> dict:
    flags = sorted(set(FLAG_RE.findall(help_text)))
    commands: set[str] = set()
    in_commands = False
    for line in help_text.splitlines():
        low = line.strip().lower()
        if low.startswith("commands:") or low.startswith("available commands"):
            in_commands = True
            continue
        if in_commands and line.strip() and not line.startswith(" ") and not line.startswith("\t"):
            if low.startswith("options:") or low.startswith("usage:"):
                in_commands = False
                continue
        if in_commands:
            tok = line.strip().split()
            if tok:
                name = tok[0].strip(",")
                if re.fullmatch(r"[a-z][a-z0-9-]+", name):
                    commands.add(name)
        # commander-style "  cmd  Description"
        m = re.match(r"^\s{2}([a-z][a-z0-9-]+)\s{2,}", line)
        if m:
            commands.add(m.group(1))
    return {"flags": flags, "commands": sorted(commands), "text": help_text}


def harvest(launcher: Path, index_js: Path | None) -> dict:
    wrapper_text = launcher.read_text(encoding="utf-8", errors="replace") if launcher.is_file() else ""
    wrap_env = wrapper_env_names(wrapper_text)
    js_env: list[str] = []
    flags: list[str] = []
    index_bytes = 0
    if index_js and index_js.is_file():
        index_bytes = index_js.stat().st_size
        env_names: set[str] = set()
        flag_names: set[str] = set()
        with index_js.open("rb") as fh:
            while True:
                chunk = fh.read(1024 * 1024)
                if not chunk:
                    break
                blob = chunk.decode("latin-1", errors="ignore")
                env_names.update(js_env_names(blob))
                flag_names.update(js_flags(blob))
        js_env = sorted(env_names)
        flags = sorted(flag_names)
    return {
        "wrapper_path": str(launcher),
        "wrapper_env": wrap_env,
        "index_js": str(index_js) if index_js else None,
        "index_bytes": index_bytes,
        "js_env": js_env,
        "js_flags_sample": flags[:80],
        "js_flag_count": len(flags),
    }
