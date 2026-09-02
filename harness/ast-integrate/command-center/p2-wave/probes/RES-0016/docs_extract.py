"""Second signal: parse numbers and refusal strings from frozen official docs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "docs"


def _sha(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def extract() -> dict:
    sub = FIX / "sub-agents.excerpt.md"
    env = FIX / "env-vars.excerpt.md"
    src = FIX / "SOURCE.json"
    sub_text = sub.read_text(encoding="utf-8")
    env_text = env.read_text(encoding="utf-8")
    missing = []

    if "up to three layers below the main conversation" not in sub_text:
        missing.append("depth-prose-three-layers")
    if "withholds the `Agent` tool" not in sub_text:
        missing.append("depth-withhold")
    if "the tool returns an error instead of spawning" not in sub_text:
        missing.append("depth-fork-error")
    if "Concurrent subagent limit reached" not in sub_text:
        missing.append("concurrent-refusal-verbatim")
    if "when 20 subagents are running in a session" not in sub_text:
        missing.append("concurrent-prose-20")
    if "If you leave it unset, the subagent inherits the main conversation's mode" not in sub_text:
        missing.append("inherit-when-unset")
    if "If the parent uses `bypassPermissions` or `acceptEdits`, this takes precedence and can't be overridden" not in sub_text:
        missing.append("sticky-parent-modes")
    if "the subagent inherits auto mode and any `permissionMode` in its frontmatter is ignored" not in sub_text:
        missing.append("auto-sticky")

    depth_env = re.search(
        r"CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH[\s\S]*?\(default:\s*(\d+)\)",
        env_text,
    )
    conc_env = re.search(
        r"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS[\s\S]*?\(default:\s*(\d+)\)",
        env_text,
    )
    if depth_env is None:
        missing.append("env-depth-default")
    if conc_env is None:
        missing.append("env-concurrent-default")
    if "Removed in v2.1.224 and now a no-op" not in env_text:
        missing.append("per-session-cap-removed")
    if missing:
        raise RuntimeError("docs extract missing: " + ",".join(missing))

    depth_default = int(depth_env.group(1))
    concurrent_default = int(conc_env.group(1))
    if depth_default != 3 or concurrent_default != 20:
        raise RuntimeError(
            f"docs extract unexpected defaults depth={depth_default} concurrent={concurrent_default}"
        )
    source = json.loads(src.read_text(encoding="utf-8"))
    return {
        "ok": True,
        "depth_default": depth_default,
        "concurrent_default": concurrent_default,
        "concurrent_refusal": "Concurrent subagent limit reached",
        "depth_withhold_phrase": "withholds the `Agent` tool",
        "fork_depth_refusal": "the tool returns an error instead of spawning",
        "inherit_when_unset": True,
        "sticky_parent_modes": ["bypassPermissions", "acceptEdits", "auto"],
        "per_session_cap_removed": True,
        "env_depth": "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH",
        "env_concurrent": "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS",
        "non_digit_ignored": True,
        "files": {
            "sub-agents.excerpt.md": {
                "path": "command-center/p2-wave/probes/RES-0016/fixtures/docs/sub-agents.excerpt.md",
                "sha256": _sha(sub),
                "bytes": sub.stat().st_size,
            },
            "env-vars.excerpt.md": {
                "path": "command-center/p2-wave/probes/RES-0016/fixtures/docs/env-vars.excerpt.md",
                "sha256": _sha(env),
                "bytes": env.stat().st_size,
            },
        },
        "source": source,
    }
