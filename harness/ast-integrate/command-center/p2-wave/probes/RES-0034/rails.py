#!/usr/bin/env python3
"""Vendor-faithful local rails for documented locator/parser leaks.

These rails reconstruct documented load rules. They are not live `claude` /
`codex` CLI processes and do not touch API keys.

Claude Code (anthropic/claude-code):
  * JSON objects: unknown keys are ignored.
  * Instructions: CLAUDE.md.
  * Plugins: .claude-plugin/plugin.json.

OpenAI Codex (openai/codex):
  * JSON objects: unknown keys fail closed (serde deny_unknown_fields).
    A failed hooks load surfaces as a successful empty inventory — the
    silent-corruption shape named by RES-0023.
  * Instructions: AGENTS.md.
  * Plugins: .codex-plugin/plugin.json.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

CLAUDE = "anthropic/claude-code"
CODEX = "openai/codex"
RAIL_IDS = (CLAUDE, CODEX)

HOOKS_ALLOWED = frozenset({"hooks"})
PORTABLE_ALLOWED = frozenset({"name", "version"})
MUST_NOT_RE = re.compile(r"MUST-NOT:\s*(\S+)")


class RailError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise RailError(f"missing {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RailError(f"expected object in {path}")
    return data


def _hook_ids(data: dict[str, Any] | None) -> list[str]:
    if not data:
        return []
    hooks = data.get("hooks") or []
    if not isinstance(hooks, list):
        return []
    out: list[str] = []
    for item in hooks:
        if isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    return out


def load_json_permissive(path: Path, allowed: frozenset[str]) -> tuple[dict[str, Any], list[str]]:
    data = _read_json(path)
    extra = sorted(k for k in data if k not in allowed)
    kept = {k: v for k, v in data.items() if k in allowed}
    return kept, extra


def load_json_strict(
    path: Path, allowed: frozenset[str], *, fail_closed: bool = True
) -> tuple[dict[str, Any] | None, list[str]]:
    data = _read_json(path)
    extra = sorted(k for k in data if k not in allowed)
    if extra and fail_closed:
        return None, extra
    kept = {k: v for k, v in data.items() if k in allowed}
    return kept, extra


def claude_hooks(root: Path) -> dict[str, Any]:
    kept, extra = load_json_permissive(root / "hooks.json", HOOKS_ALLOWED)
    return {
        "ok": True,
        "armed_hook_ids": _hook_ids(kept),
        "ignored_keys": extra,
        "locator": "hooks.json",
    }


def codex_hooks(root: Path, *, fail_closed: bool = True) -> dict[str, Any]:
    kept, extra = load_json_strict(
        root / "hooks.json", HOOKS_ALLOWED, fail_closed=fail_closed
    )
    if extra and fail_closed:
        # Successful-looking empty inventory: the silent-corruption shape.
        return {
            "ok": True,
            "armed_hook_ids": [],
            "ignored_keys": [],
            "locator": "hooks.json",
            "strict_unknown_keys": extra,
            "load_mode": "deny_unknown_fields_empty_success",
        }
    return {
        "ok": True,
        "armed_hook_ids": _hook_ids(kept),
        "ignored_keys": extra,
        "locator": "hooks.json",
        "load_mode": "accepted",
    }


def _must_not(path: Path) -> str:
    if not path.is_file():
        return ""
    match = MUST_NOT_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


def claude_instructions(root: Path) -> dict[str, Any]:
    path = root / "CLAUDE.md"
    token = _must_not(path)
    return {
        "ok": True,
        "must_not": token,
        "source": "CLAUDE.md",
        "found": bool(token),
    }


def codex_instructions(root: Path) -> dict[str, Any]:
    path = root / "AGENTS.md"
    token = _must_not(path)
    return {
        "ok": True,
        "must_not": token,
        "source": "AGENTS.md",
        "found": bool(token),
    }


def _plugin_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and data.get("id"):
        return [str(data["id"])]
    return []


def claude_plugins(root: Path) -> dict[str, Any]:
    loc = ".claude-plugin/plugin.json"
    return {
        "ok": True,
        "plugin_ids": _plugin_ids(root / ".claude-plugin" / "plugin.json"),
        "locator": loc,
    }


def codex_plugins(root: Path) -> dict[str, Any]:
    loc = ".codex-plugin/plugin.json"
    return {
        "ok": True,
        "plugin_ids": _plugin_ids(root / ".codex-plugin" / "plugin.json"),
        "locator": loc,
    }


def portable_identity(root: Path) -> dict[str, Any]:
    kept, extra = load_json_strict(
        root / "portable.json", PORTABLE_ALLOWED, fail_closed=True
    )
    if extra or kept is None:
        return {
            "ok": False,
            "name": None,
            "version": None,
            "unknown_keys": extra,
        }
    return {
        "ok": True,
        "name": kept.get("name"),
        "version": kept.get("version"),
        "unknown_keys": extra,
    }


Dispatch = Callable[..., dict[str, Any]]

HANDLERS: dict[str, dict[str, Dispatch]] = {
    CLAUDE: {
        "hooks": claude_hooks,
        "instructions": claude_instructions,
        "plugins": claude_plugins,
        "portable": portable_identity,
    },
    CODEX: {
        "hooks": codex_hooks,
        "instructions": codex_instructions,
        "plugins": codex_plugins,
        "portable": portable_identity,
    },
}


def run_rail(
    rail_id: str, kind: str, root: Path, **kwargs: Any
) -> dict[str, Any]:
    table = HANDLERS.get(rail_id)
    if table is None:
        raise RailError(f"unknown rail {rail_id}")
    fn = table.get(kind)
    if fn is None:
        raise RailError(f"unknown kind {kind} for {rail_id}")
    return fn(root, **kwargs)
