"""monitorcore.monitors — the ``monitors.toml`` registry, trigger-matching, and launch-builder.

The shared, 100%-gated CORE behind the generalized ``mon <name>`` launcher (``mon.cmd``) and the
generalized ``monitor-autolaunch`` hook. Everything here is pure + deterministic:

- :class:`MonitorSpec` — one registered monitor (``name`` / ``dir`` / ``entry`` / ``trigger_tool``).
- :func:`load_monitors` — parse a ``monitors.toml`` registry with the stdlib ``tomllib`` (NEVER
  ``tomlkit`` — this module only READS; the ``~/.agents`` sync is a file copy, not a TOML rewrite,
  so a write-round-trip dep would needlessly ImportError the vendored stdlib-only skill).
- :func:`match_triggers` — the registered monitors whose ``trigger_tool`` fires for a given tool.
- :func:`resolve_entry` — the absolute path of a monitor's entry script under the skills root.
- :func:`build_wt_argv` / :func:`build_console_argv` / :func:`launch_argvs` — the Windows-Terminal
  → plain-console launch ladder (argv only).

The subprocess boundary in :func:`launch` / :func:`main` is INJECTED as ``runner`` (default
``subprocess.Popen``), so tests drive every rung with a FAKE runner that records argv WITHOUT
opening a real window (the ``pdf.py`` / ``spawn.py`` template). The interpreter is read through
:func:`_py` so tests monkeypatch ``sys.executable`` and exercise both the resolved and the
fallback path deterministically on any OS.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass

__all__ = [
    "MonitorSpec",
    "build_console_argv",
    "build_wt_argv",
    "default_monitors_path",
    "default_skills_root",
    "launch",
    "launch_argvs",
    "load_monitors",
    "main",
    "match_triggers",
    "resolve_entry",
]

# Env override for the registry path (else the deployed monitor-launcher copy).
_ENV_TOML = "MONITORCORE_MONITORS_TOML"


@dataclass(frozen=True)
class MonitorSpec:
    """A single registered monitor from ``monitors.toml``."""

    name: str
    dir: str
    entry: str
    trigger_tool: str


def _py() -> str:
    """The current interpreter, falling back to bare ``python`` if unresolved."""
    return sys.executable or "python"


def default_skills_root() -> str:
    """The deployed skills root (``~/.agents/skills``) that holds each monitor's ``dir``."""
    return os.path.join(os.path.expanduser("~"), ".agents", "skills")


def default_monitors_path() -> str:
    """The registry path: the ``MONITORCORE_MONITORS_TOML`` override, else the deployed copy."""
    override = os.environ.get(_ENV_TOML)
    if override:
        return override
    return os.path.join(default_skills_root(), "monitor-launcher", "monitors.toml")


def load_monitors(path: str) -> dict[str, MonitorSpec]:
    """Parse a ``monitors.toml`` registry (stdlib ``tomllib``) into ``{name: MonitorSpec}``.

    Each top-level ``[table]`` is one monitor; a non-table top-level key (e.g. a stray scalar)
    is ignored. Missing ``dir`` / ``entry`` / ``trigger_tool`` default to ``""``.
    """
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    specs: dict[str, MonitorSpec] = {}
    for name, tbl in data.items():
        if not isinstance(tbl, dict):
            continue
        specs[name] = MonitorSpec(
            name=name,
            dir=str(tbl.get("dir", "")),
            entry=str(tbl.get("entry", "")),
            trigger_tool=str(tbl.get("trigger_tool", "")),
        )
    return specs


def match_triggers(specs: dict[str, MonitorSpec], tool_name: str) -> list[MonitorSpec]:
    """The monitors whose ``trigger_tool`` equals ``tool_name`` (empty triggers never match)."""
    return [s for s in specs.values() if s.trigger_tool and s.trigger_tool == tool_name]


def resolve_entry(spec: MonitorSpec, skills_root: str) -> str:
    """The absolute path of ``spec``'s entry script: ``<skills_root>/<dir>/<entry>``."""
    return os.path.join(skills_root, spec.dir, spec.entry)


def build_wt_argv(
    name: str, entry: str, args=(), *, py: str | None = None
) -> list[str]:
    """Windows-Terminal argv: a new tab in the reusable ``<name>`` window running ``entry``."""
    py = py or _py()
    return ["wt", "-w", name, "new-tab", "--title", name, py, entry, *args]


def build_console_argv(
    name: str, entry: str, args=(), *, py: str | None = None
) -> list[str]:
    """Plain-console fallback argv (``cmd /c start``) when Windows-Terminal is absent."""
    py = py or _py()
    return ["cmd", "/c", "start", name, py, entry, *args]


def launch_argvs(
    name: str, entry: str, args=(), *, py: str | None = None
) -> list[list[str]]:
    """The launch ladder for ``entry``: Windows-Terminal first, plain console fallback."""
    return [
        build_wt_argv(name, entry, args, py=py),
        build_console_argv(name, entry, args, py=py),
    ]


def launch(
    name: str,
    entry: str,
    args=(),
    *,
    py: str | None = None,
    runner=subprocess.Popen,
    **popen_kw,
) -> list[str] | None:
    """Open ``entry`` via ``runner``, walking the ladder; return the argv that launched or ``None``.

    Each rung is tried in turn; on any failure the next rung is attempted, and if every rung
    fails ``None`` is returned. ``runner`` is injected (default ``subprocess.Popen``) so tests
    drive every branch with a fake that never opens a window.
    """
    for argv in launch_argvs(name, entry, args, py=py):
        try:
            runner(argv, **popen_kw)
            return argv
        except Exception:  # noqa: BLE001 — try the next rung
            continue
    return None


def main(
    argv: list[str] | None = None,
    *,
    monitors_path: str | None = None,
    skills_root: str | None = None,
    runner=subprocess.Popen,
) -> int:
    """``mon <name> [args...]`` — launch a registered monitor. Returns a process exit code.

    ``2`` = no monitor named; ``1`` = unknown monitor or launch failed; ``0`` = launched. The
    registry path, skills root, and subprocess runner are injectable for tests.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: mon <name> [args...]")
        return 2
    name, rest = args[0], args[1:]
    specs = load_monitors(monitors_path or default_monitors_path())
    spec = specs.get(name)
    if spec is None:
        known = ", ".join(sorted(specs)) or "none"
        print(f"unknown monitor: {name} (known: {known})")
        return 1
    entry = resolve_entry(spec, skills_root or default_skills_root())
    launched = launch(name, entry, rest, runner=runner)
    if launched is None:
        print(f"failed to launch {name}")
        return 1
    print(f"launched {name}: {' '.join(launched)}")
    return 0


if __name__ == "__main__":  # pragma: no cover -- module CLI entry (mon.cmd → python -m)
    raise SystemExit(main())
