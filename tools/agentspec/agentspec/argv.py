"""ARGV construction that REFUSES to place a prompt on the command line.

MEASURED FAILURE THIS EXISTS FOR: an inline prompt produced ``payload_len=34472`` and killed
the run with Windows ``os error 206``. The Windows ``CreateProcess`` command-line cap is
**32,767** chars, measured via a libuv spawn sweep at **32,745 OK -> 32,774 ENAMETOOLONG**.
That measurement lives in this repo at ``tools/glob-argv-guard/glob_argv_guard.py`` (its
``WINDOWS_CMDLINE_CAP`` plus the ``n=1127``/``n=1128`` comment); ``tests/test_argv.py`` parses
that file and asserts our constant still equals it, so the two cannot drift and neither
invents a number.

A prompt therefore travels by FILE or by STDIN. Never argv. :func:`prompt_on_argv` decides that
with three rules, in order of precision — a first draft used bare substring containment at every
length and FALSE-POSITIVED on a one-char prompt hiding inside ``--output-last-message``, i.e. a
guard that blocked valid work. A detector that fires in the good state is as broken as one that
stays silent in the bad state, so the rules are now:

1. ``element == prompt`` — the prompt passed as a bare argument. Always a violation, any length.
2. ``element`` ends with ``=`` / ``:`` + the prompt — the ``--message=<body>`` shape. Always a
   violation, any length.
3. bare containment, but only once ``len(prompt) >= MIN_SUBSTRING_SCAN_LEN``. The threshold
   exists solely to stop a short prompt colliding with a flag token; the measured failure was
   34,472 chars, three orders of magnitude above it, so nothing this guard was built for can
   slip under it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

WINDOWS_CMDLINE_CAP = 32767
"""Mirrors tools/glob-argv-guard/glob_argv_guard.py; the drift is gated by a test."""

PROMPT_TRANSPORTS: tuple[str, ...] = ("file", "stdin")

MIN_SUBSTRING_SCAN_LEN = 64
"""Below this, only equality and the ``=``/``:`` shapes are checked (see the module docstring)."""

_VALUE_DELIMITERS: tuple[str, ...] = ("=", ":")


class PromptOnArgv(ValueError):
    """The prompt reached argv. Unrecoverable by retry — the caller must be fixed."""

    reason = "policy-violation"


class ArgvTooLong(ValueError):
    """The rendered command line exceeds the platform cap."""

    reason = "win-arg-limit"

    def __init__(self, *, cmdline_len: int, cap: int) -> None:
        super().__init__(
            f"win-arg-limit: command line is {cmdline_len} chars, cap is {cap}"
        )
        self.cmdline_len = cmdline_len
        self.cap = cap


class PolicyViolation(ValueError):
    """A required hardening flag is absent from a non-interactive invocation."""

    reason = "policy-violation"

    def __init__(self, missing: tuple[str, ...]) -> None:
        super().__init__(f"policy-violation: missing hardening flags {list(missing)}")
        self.missing = missing


@dataclass(frozen=True, slots=True)
class RailSpec:
    """The declarative shape of a rail, so adding a rail is a config row, not new code.

    ``hardening`` is the load-bearing field: for a non-interactive codex call it holds
    ``--ignore-user-config``, whose absence blew the argv limit by pulling the whole active
    MCP inventory onto the command line.
    """

    name: str
    exe: str
    hardening: tuple[str, ...] = ()
    prompt_transport: str = "file"
    prompt_flag: str | None = None
    cap: int = WINDOWS_CMDLINE_CAP


@dataclass(frozen=True, slots=True)
class ArgvPlan:
    """A validated dispatch plan. The prompt is in ``prompt_path`` or ``stdin_payload``."""

    argv: tuple[str, ...]
    prompt_transport: str
    prompt_path: str | None
    stdin_payload: str | None
    cmdline_len: int


def render_cmdline(argv: Sequence[str]) -> str:
    """Render ``argv`` the way Windows would, so the length check measures the real thing."""
    return " ".join(_quote(element) for element in argv)


def build_argv(
    *,
    exe: str,
    prompt: str,
    transport: str,
    flags: Sequence[str] = (),
    prompt_flag: str | None = None,
    prompt_path: str | None = None,
    cap: int = WINDOWS_CMDLINE_CAP,
) -> ArgvPlan:
    """Build a dispatch plan, refusing any shape that could put the prompt on argv."""
    if not exe:
        raise ValueError("exe must be non-empty")
    if not prompt:
        raise ValueError("prompt must be non-empty")
    if transport not in PROMPT_TRANSPORTS:
        raise ValueError(
            f"transport must be one of {list(PROMPT_TRANSPORTS)}, got {transport!r}"
        )

    if transport == "file":
        if not prompt_flag:
            raise ValueError("prompt_flag is required for the file transport")
        if not prompt_path:
            raise ValueError("prompt_path is required for the file transport")
        argv = (exe, *flags, prompt_flag, prompt_path)
        stdin_payload = None
    else:
        if prompt_path is not None:
            raise ValueError("prompt_path must be None for the stdin transport")
        if prompt_flag is not None:
            raise ValueError("prompt_flag must be None for the stdin transport")
        argv = (exe, *flags)
        stdin_payload = prompt

    for element in argv:
        if prompt_on_argv(element, prompt):
            raise PromptOnArgv(
                f"the prompt ({len(prompt)} chars) appears in argv element {element[:40]!r}; "
                "route it to a file or stdin"
            )

    cmdline_len = len(render_cmdline(argv))
    if cmdline_len > cap:
        raise ArgvTooLong(cmdline_len=cmdline_len, cap=cap)

    return ArgvPlan(
        argv=argv,
        prompt_transport=transport,
        prompt_path=prompt_path,
        stdin_payload=stdin_payload,
        cmdline_len=cmdline_len,
    )


def build_for_rail(
    rail: RailSpec,
    *,
    prompt: str,
    prompt_path: str | None = None,
    flags: Sequence[str] = (),
    inject_hardening: bool = True,
) -> ArgvPlan:
    """Build a plan for ``rail``, injecting and then VERIFYING its hardening flags.

    ``inject_hardening=False`` exists so a test can prove the verification fires; production
    callers never pass it. With it off, a rail declaring hardening raises
    :class:`PolicyViolation` — that is R5's RED condition.
    """
    if rail.prompt_transport not in PROMPT_TRANSPORTS:
        raise ValueError(
            f"rail {rail.name!r} declares an unknown transport {rail.prompt_transport!r}"
        )
    effective = (*flags, *rail.hardening) if inject_hardening else tuple(flags)
    missing = missing_hardening((rail.exe, *effective), rail.hardening)
    if missing:
        raise PolicyViolation(missing)
    if rail.prompt_transport == "file":
        return build_argv(
            exe=rail.exe,
            prompt=prompt,
            transport="file",
            flags=effective,
            prompt_flag=rail.prompt_flag,
            prompt_path=prompt_path,
            cap=rail.cap,
        )
    return build_argv(
        exe=rail.exe, prompt=prompt, transport="stdin", flags=effective, cap=rail.cap
    )


def missing_hardening(argv: Sequence[str], required: Sequence[str]) -> tuple[str, ...]:
    """Which ``required`` flags are absent from ``argv``, matched as WHOLE elements.

    Whole-element matching is deliberate: ``--ignore-user-configuration`` must not satisfy
    ``--ignore-user-config``. A substring matcher is the measured near-miss class.
    """
    present = set(argv)
    return tuple(flag for flag in required if flag not in present)


def prompt_on_argv(element: str, prompt: str) -> bool:
    """True when ``element`` carries ``prompt``. See the module docstring for the three rules."""
    if element == prompt:
        return True
    for delimiter in _VALUE_DELIMITERS:
        if element.endswith(delimiter + prompt):
            return True
    return len(prompt) >= MIN_SUBSTRING_SCAN_LEN and prompt in element


def _quote(element: str) -> str:
    if element == "" or any(ch.isspace() for ch in element):
        return f'"{element}"'
    return element
