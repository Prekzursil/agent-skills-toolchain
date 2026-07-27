"""The injected PORTS -- every impure edge agentrail has, declared as a Protocol.

There are exactly three: the filesystem, the process spawn, and a warning sink. A clock is a
fourth, but agentspec already owns that port (:class:`agentspec.clock.Clock`) so it is imported
rather than redeclared.

The split is what makes the 100% line+branch bar reachable with ZERO ``# pragma: no cover``:
the pure layer (rails / resolve / plan / report / deploy) only ever sees these Protocols, so a
test drives every branch with an in-memory fake, and the real bindings in
:mod:`agentrail.runner` are thin enough to be measured with an injected stdlib callable or a
``tmp_path``. The gated suite therefore performs NO network I/O and spawns NO real process.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@runtime_checkable
class RailFileSystem(Protocol):
    """Filesystem access for rail resolution, prompt spilling and receipt reading.

    NOT reused from ``tools/taskwatch_monitor/core/adapters.py``'s ``FileSystem``, deliberately.
    That one is a ``stat``/``read_text``/``glob`` surface whose ``read_text`` RAISES on absence;
    this one needs BYTE reads (a receipt is bytes until the oracle decodes it), a WRITE (the
    prompt spill), and total absence semantics (``None``, never an exception, because a missing
    receipt is a taxonomy reason and not an error path). taskwatch_monitor is also a separate
    distribution with no dependency edge to this one, so importing it would add a package
    dependency -- and a second basedpyright ``extraPaths`` entry -- for a monitoring concern a
    dispatch shell does not have. The name differs so the two cannot be confused.
    """

    def glob(self, pattern: str) -> tuple[str, ...]:
        """Absolute paths matching ``pattern``, SORTED so resolution is deterministic."""
        ...

    def is_file(self, path: str) -> bool:
        """True when ``path`` names an existing regular file."""
        ...

    def read_bytes(self, path: str) -> bytes | None:
        """The file's bytes, or ``None`` when it does not exist."""
        ...

    def write_text(self, path: str, text: str) -> None:
        """Create parent directories as needed and write ``text`` as UTF-8."""
        ...


@dataclass(frozen=True, slots=True)
class SpawnOutcome:
    """What a spawn port hands back BEFORE the oracle looks at it.

    Deliberately NOT :class:`agentspec.oracle.RailResult`: this is the transport's raw report,
    including the transport-level failure (``error_reason``) that never reaches the oracle
    because no process ever ran. :mod:`agentrail.report` is the one place that projects this
    onto agentspec's types.

    ``error_reason`` MUST be a member of the closed agentspec taxonomy or ``None``;
    :func:`agentrail.report.spawn_failure` enforces that and there is a mutation row for it.
    """

    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""
    error_reason: str | None = None
    detail: str = ""


@runtime_checkable
class Spawn(Protocol):
    """Run one rail process to completion. Never backgrounds -- that is a policy violation."""

    def __call__(
        self,
        *,
        argv: Sequence[str],
        stdin_payload: str | None,
        timeout_s: int,
        cwd: str | None,
    ) -> SpawnOutcome: ...


@runtime_checkable
class WarningSink(Protocol):
    """Where a degraded-but-usable decision is RECORDED rather than swallowed."""

    def warn(self, message: str) -> None: ...


@dataclass(slots=True)
class CollectingWarnings:
    """A :class:`WarningSink` that keeps every message, so a test can assert on it.

    This is the DEFAULT sink, not a test double: a warning that is only printed is a warning a
    caller cannot act on, and the resolution warning ("fell back to the npm shim") has to reach
    the result envelope's ``artifacts``/``summary``, not just a console.
    """

    messages: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        self.messages.append(message)

    def drain(self) -> tuple[str, ...]:
        """Return the collected messages and reset, so one sink can serve several calls."""
        collected = tuple(self.messages)
        self.messages.clear()
        return collected
