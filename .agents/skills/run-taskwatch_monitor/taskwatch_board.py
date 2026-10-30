#!/usr/bin/env python
"""`mon taskwatch` — the registry's front door to taskwatch_monitor.

WHY THIS SHIM EXISTS

``taskwatch_monitor`` is a complete, tested, general-purpose long-task monitor
that nothing could reach. It had no stanza in ``monitors.toml``, so ``mon``
could not launch it, and no hook referenced it. This file is the missing half:
a stdlib-only entry the registry can invoke, which locates taskwatch and hands
off to it.

It is a BRIDGE, not a merge. ``monitorcore`` watches agent-harness artifacts
(transcripts, manifests, MCP configs); ``taskwatch_monitor`` watches arbitrary
external jobs (logfile growth, process liveness, GPU, p50/p90 ETA from sqlite
priors). Those are different domains and stay two tools behind one front door.
Nothing here imports taskwatch, and no part of taskwatch is copied in.

WHY IT DELEGATES INSTEAD OF IMPORTING

The registry launches an entry as ``python <dir>/<entry>`` from a deployed skill
directory under ``~/.agents/skills/``, under whatever plain Python is on PATH.
``monitorcore`` can be vendored into skill dirs because its runtime dependency
list is deliberately empty. ``taskwatch_monitor`` cannot: it declares
``rich``, ``tomlkit`` and ``mcp``, and its CLI runs as ``python -m cli.app``
with relative imports from its own venv, which ``install.ps1`` creates. So
importing it here would either drag third-party packages into a stdlib-only
skill or break the moment the deployed copy drifted from the venv.

Delegating also means taskwatch keeps owning its own behaviour: this file has no
opinion about probes, templates, ETA or rendering, and will not need editing
when those change.

WHEN TASKWATCH IS NOT INSTALLED

It says so, names the one command that fixes it, and exits 3 — a distinct code
from a usage error, so a caller can tell "not set up yet" from "you typed it
wrong". It does not silently succeed, and it does not pretend to monitor
anything. Exiting 0 with an empty board would be the dishonest option.

Stdlib only, by requirement.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

#: Exit code for "taskwatch is not installed here" — deliberately distinct from
#: 2 (argparse/usage), so a launcher can branch on it.
EXIT_NOT_INSTALLED = 3

#: Default subcommand. ``status --watch`` is the live board, which is what a
#: monitor registry entry is expected to open.
DEFAULT_ARGS = ("status", "--watch")

#: Where the tool dir might be, relative to this deployed skill dir, tried in
#: order. The skill is deployed outside the repo, so the repo-relative guesses
#: only help when it is being run from a checkout.
_TOOL_DIR_GUESSES = (
    Path("../../tools/taskwatch_monitor"),
    Path("../../../source/agent-skills-toolchain/tools/taskwatch_monitor"),
)

INSTALL_HINT = (
    "taskwatch is not installed. Install it once:\n"
    "    cd <repo>/tools/taskwatch_monitor\n"
    "    pwsh -NoProfile -File ./install.ps1\n"
    "That creates its venv and puts a `taskwatch` shim on PATH. Alternatively\n"
    "set TASKWATCH_HOME to the tools/taskwatch_monitor directory, or\n"
    "TASKWATCH_CMD to an explicit executable."
)


def _is_tool_dir(path: Path) -> bool:
    """A taskwatch checkout, identified by its CLI module rather than its name."""
    return (path / "cli" / "app.py").is_file()


def resolve(
    args: tuple[str, ...] = DEFAULT_ARGS,
    *,
    env: dict[str, str] | None = None,
    which=shutil.which,
    here: Path | None = None,
) -> tuple[list[str] | None, Path | None, str]:
    """Work out how to run taskwatch. Returns ``(argv, cwd, reason)``.

    Pure apart from the injected ``which`` and filesystem probes, so every rung
    of the ladder is testable without launching anything. ``argv`` is ``None``
    when taskwatch could not be found, and ``reason`` always explains the
    outcome — including which rung matched, so a surprising launch is traceable.
    """
    environ = os.environ if env is None else env
    base = Path(__file__).resolve().parent if here is None else here

    explicit = environ.get("TASKWATCH_CMD")
    if explicit:
        return [explicit, *args], None, f"TASKWATCH_CMD={explicit}"

    found = which("taskwatch")
    if found:
        return [found, *args], None, f"taskwatch on PATH ({found})"

    home = environ.get("TASKWATCH_HOME")
    if home:
        hp = Path(home).expanduser()
        if _is_tool_dir(hp):
            return (
                [sys.executable, "-m", "cli.app", *args],
                hp,
                f"TASKWATCH_HOME={hp}",
            )
        # An explicit pointer that is wrong is a mistake worth naming, rather
        # than quietly falling through to a guess that happens to work.
        return None, None, f"TASKWATCH_HOME={hp} is not a taskwatch checkout"

    for guess in _TOOL_DIR_GUESSES:
        cand = (base / guess).resolve()
        if _is_tool_dir(cand):
            return [sys.executable, "-m", "cli.app", *args], cand, f"found at {cand}"

    return (
        None,
        None,
        "taskwatch not found on PATH, TASKWATCH_HOME, or beside this skill",
    )


def main(argv: list[str] | None = None, *, runner=subprocess.call, **kw) -> int:
    """Launch taskwatch's live board, passing through any extra arguments."""
    passthrough = tuple(sys.argv[1:] if argv is None else argv) or DEFAULT_ARGS
    cmd, cwd, reason = resolve(passthrough, **kw)
    if cmd is None:
        print(f"[taskwatch] {reason}", file=sys.stderr)
        print(INSTALL_HINT, file=sys.stderr)
        return EXIT_NOT_INSTALLED
    print(f"[taskwatch] {reason}")
    return int(runner(cmd, cwd=str(cwd) if cwd else None))


if __name__ == "__main__":  # pragma: no cover -- module CLI entrypoint
    raise SystemExit(main())
