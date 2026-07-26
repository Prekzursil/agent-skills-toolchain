"""The ONE thin filesystem shim: locate and read the five configuration documents.

Everything else in mcpctl is pure. This module is kept deliberately small and its
reader is INJECTED (``read_text``), so even the shim is exercised hermetically and
needs no ``# pragma: no cover``. One test binds the real default reader against a
``tmp_path`` so the production default is proven, not merely seamed around.

READ-ONLY by construction: there is no write, no ``open(..., "w")``, no ``mkdir``, no
``os.replace`` anywhere in this package. Live mutation is a later work unit.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from mcpctl.safety import safe
from mcpctl.topology import SourceDocs

__all__ = [
    "SourcePaths",
    "SourceProblem",
    "default_home",
    "load_sources",
    "project_key_for",
    "source_paths",
]


@dataclass(frozen=True)
class SourcePaths:
    """Where each configuration scope lives, relative to a home directory."""

    claude_json: Path
    mcp_json: Path
    settings: Path
    settings_local: Path
    disabled_defaults: Path

    def as_tuple(self) -> tuple[tuple[str, Path], ...]:
        """``(label, path)`` pairs in a stable order, for iteration and reporting."""
        return (
            ("claude_json", self.claude_json),
            ("mcp_json", self.mcp_json),
            ("settings", self.settings),
            ("settings_local", self.settings_local),
            ("disabled_defaults", self.disabled_defaults),
        )


@dataclass(frozen=True)
class SourceProblem:
    """A source that exists but could not be used. Absence is NOT a problem."""

    label: str
    path: str
    reason: str


def source_paths(home: Path) -> SourcePaths:
    """Build the five scope paths under ``home``."""
    return SourcePaths(
        claude_json=home / ".claude.json",
        mcp_json=home / ".mcp.json",
        settings=home / ".claude" / "settings.json",
        settings_local=home / ".claude" / "settings.local.json",
        disabled_defaults=home / ".claude" / ".mcp-disabled-defaults.json",
    )


def default_home() -> Path:
    """The user's home directory, expanded the same way the host application does."""
    return Path(os.path.expanduser("~"))


def project_key_for(cwd: Path) -> str:
    """The ``projects`` key for ``cwd``: an absolute path with forward slashes.

    Claude Code keys ``projects`` by the session's EXACT cwd, so this performs no
    ancestor walk. :func:`mcpctl.topology.project_row` enforces the same rule.
    """
    return str(cwd).replace("\\", "/")


def _default_read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_sources(
    paths: SourcePaths,
    *,
    read_text: Callable[[Path], str] = _default_read_text,
) -> tuple[SourceDocs, tuple[SourceProblem, ...]]:
    """Read + parse every scope. Returns the docs plus a list of real problems.

    An absent file yields ``None`` for that scope and NO problem -- most boxes will not
    have all five. A present-but-unusable file (bad JSON, wrong top-level type, no read
    permission) yields ``None`` plus a :class:`SourceProblem`, so the caller can degrade
    to a ``warning`` envelope instead of silently reporting a partial inventory as
    complete.
    """
    loaded: dict[str, object] = {}
    problems: list[SourceProblem] = []
    for label, path in paths.as_tuple():
        try:
            raw = read_text(path)
        except FileNotFoundError:
            loaded[label] = None
            continue
        except OSError as exc:
            loaded[label] = None
            problems.append(
                SourceProblem(
                    label=label,
                    path=safe(str(path)),
                    reason=safe(f"{type(exc).__name__}: {exc}"),
                )
            )
            continue
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as exc:
            loaded[label] = None
            problems.append(
                SourceProblem(
                    label=label,
                    path=safe(str(path)),
                    reason=safe(f"JSONDecodeError: {exc}"),
                )
            )
            continue
        if not isinstance(doc, dict):
            loaded[label] = None
            problems.append(
                SourceProblem(
                    label=label,
                    path=safe(str(path)),
                    reason=f"expected a JSON object at the top level, got {type(doc).__name__}",
                )
            )
            continue
        loaded[label] = doc
    return (
        SourceDocs(
            claude_json=loaded["claude_json"],
            mcp_json=loaded["mcp_json"],
            settings=loaded["settings"],
            settings_local=loaded["settings_local"],
            disabled_defaults=loaded["disabled_defaults"],
        ),
        tuple(problems),
    )
