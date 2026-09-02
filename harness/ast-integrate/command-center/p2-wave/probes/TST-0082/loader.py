"""Codex-strict hooks.json loader.

Measured precedent (spec:11303): a top-level $schema key made Codex load ZERO
hooks while the plugin files still looked installed. A tolerant reader that
skips unknown keys would still see the registered commands. This loader keeps
both views so the probe can tell registration from execution and installed
from loaded.
"""
from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

import scenario as S

REPO = S.REPO
ALLOWED_TOP_LEVEL = frozenset({"hooks"})


def _script_exists(command: str) -> bool:
    argv = shlex.split(command)
    for token in argv:
        if token.endswith(".py"):
            rel = token.replace("\\", "/")
            return (REPO / rel).is_file()
    return S.writer_path().is_file()


def appearance(hooks_path: Path | None = None) -> dict[str, Any]:
    """Filesystem claim that a plugin is installed. Not evidence of loading."""
    writer = S.writer_path().is_file()
    manifest = S.manifest_path().is_file()
    cfg = hooks_path if hooks_path is not None else S.healthy_path()
    return {
        "hook_writer_present": writer,
        "manifest_present": manifest,
        "hooks_json_present": cfg.is_file(),
        "hooks_json_path": (
            cfg.relative_to(REPO).as_posix() if cfg.is_absolute() else str(cfg)
        ),
        "looks_installed": writer and manifest and cfg.is_file(),
    }


def _entries(hooks_obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(hooks_obj, dict):
        return out
    for event, matchers in hooks_obj.items():
        if not isinstance(matchers, list):
            continue
        for matcher_row in matchers:
            if not isinstance(matcher_row, dict):
                continue
            matcher = matcher_row.get("matcher") or "*"
            for hook in matcher_row.get("hooks") or []:
                if not isinstance(hook, dict):
                    continue
                if hook.get("type") != "command":
                    continue
                command = hook.get("command")
                if not isinstance(command, str) or not command.strip():
                    continue
                argv = shlex.split(command)
                hook_id = argv[-1] if len(argv) >= 2 else str(event)
                out.append(
                    {
                        "event": str(event),
                        "matcher": str(matcher),
                        "command": command,
                        "argv": argv,
                        "hook_id": hook_id,
                        "script_exists": _script_exists(command),
                    }
                )
    return out


def load(path: Path) -> dict[str, Any]:
    """Strict load: any unknown top-level key yields zero loaded hooks."""
    rel = path.relative_to(REPO).as_posix() if path.is_absolute() else str(path)
    if not path.is_file():
        return {
            "path": rel,
            "installed_appearance": False,
            "parse_ok": False,
            "rejected_keys": [],
            "registered": [],
            "loaded": [],
            "reason": "hooks-json-absent",
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {
            "path": rel,
            "installed_appearance": True,
            "parse_ok": False,
            "rejected_keys": [],
            "registered": [],
            "loaded": [],
            "reason": "hooks-json-not-object",
        }
    extra = sorted(set(doc.keys()) - ALLOWED_TOP_LEVEL)
    registered = _entries(doc.get("hooks"))
    installed = path.is_file() and all(row["script_exists"] for row in registered)
    if extra:
        return {
            "path": rel,
            "installed_appearance": installed or path.is_file(),
            "parse_ok": True,
            "rejected_keys": extra,
            "registered": registered,
            "loaded": [],
            "reason": "strict-parser-rejected-keys:" + ",".join(extra),
        }
    return {
        "path": rel,
        "installed_appearance": installed,
        "parse_ok": True,
        "rejected_keys": [],
        "registered": registered,
        "loaded": list(registered),
        "reason": "strict-load-ok",
    }


def naive_file_count() -> dict[str, int]:
    """Directory listing. Same for healthy and malformed; must not be the pass signal."""
    writer = 1 if S.writer_path().is_file() else 0
    man = 1 if S.manifest_path().is_file() else 0
    return {
        "hook_writer": writer,
        "manifest": man,
        "healthy_hooks_json": 1 if S.healthy_path().is_file() else 0,
        "malformed_hooks_json": 1 if S.malformed_path().is_file() else 0,
        "sum": writer + man,
    }
