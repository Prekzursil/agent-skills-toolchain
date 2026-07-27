"""DYNAMIC executable resolution. PURE given an injected :class:`~agentrail.ports.RailFileSystem`.

RECORDED DEFECT THIS EXISTS FOR: the codex executable lives at

    AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/
        vendor/x86_64-pc-windows-msvc/bin/codex.exe

Two segments of that path are volatile -- the npm package version bumps the tree and the target
triple changes with the platform -- so pinning today's resolved string is a defect that goes
undetected until the next ``npm -g update``. Rails therefore declare GLOBS, matched in order,
and the resolver falls back to the npm shim (``codex.cmd``) only with a LOGGED WARNING: the shim
works, but it hops through an extra Node process and needs ``node`` on PATH, so a silent
downgrade would hide a real degradation.

MEASURED DETECTOR TRAP (worth carrying, it cost a scout a false negative): the login shell
aliases ``ls`` with ``-F``, so ``$(ls -d <glob>)`` appends a ``*`` classifier and the caller
reports ``exit=127 No such file or directory`` for a file that exists. Resolution is done here
against a filesystem PORT for exactly that reason -- never by shelling out.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentspec.taxonomy import env_missing

from agentrail.ports import RailFileSystem, WarningSink
from agentrail.rails import RailRow

RESOLUTION_SOURCES: tuple[str, ...] = ("glob", "fallback")
"""How an executable was found. ``fallback`` is degraded-but-usable and always warns."""


class ExecutableNotFound(LookupError):
    """No glob matched and no fallback exists. Carries a CLOSED-taxonomy reason."""

    def __init__(self, rail_name: str, tried: tuple[str, ...]) -> None:
        self.rail_name = rail_name
        self.tried = tried
        self.reason = env_missing(rail_name)
        super().__init__(
            f"{self.reason}: no executable for rail {rail_name!r}; tried {list(tried)}"
        )


@dataclass(frozen=True, slots=True)
class Resolution:
    """A resolved executable plus HOW it was found, so a degradation is visible downstream."""

    rail_name: str
    exe: str
    source: str
    tried: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def degraded(self) -> bool:
        """True when the primary glob missed and a fallback carried the call."""
        return self.source == "fallback"


def resolve(
    row: RailRow, fs: RailFileSystem, *, sink: WarningSink | None = None
) -> Resolution:
    """Resolve ``row``'s executable: globs first, in order, then fallbacks with a warning.

    Raises :class:`ExecutableNotFound` when nothing resolves. Deliberately a raise and not a
    ``None``: an unresolvable rail is not a dispatch that failed, it is a dispatch that must
    never be attempted, and :func:`agentrail.report.resolution_failure` renders it as an
    envelope with ``env-missing-<rail>``.
    """
    tried: list[str] = []
    for pattern in row.exe_globs:
        tried.append(pattern)
        matches = tuple(match for match in fs.glob(pattern) if fs.is_file(match))
        if matches:
            return Resolution(
                rail_name=row.name,
                exe=matches[0],
                source="glob",
                tried=tuple(tried),
            )

    for candidate in row.exe_fallbacks:
        tried.append(candidate)
        if fs.is_file(candidate):
            message = _fallback_warning(row.name, candidate, row.exe_globs)
            if sink is not None:
                sink.warn(message)
            return Resolution(
                rail_name=row.name,
                exe=candidate,
                source="fallback",
                tried=tuple(tried),
                warnings=(message,),
            )

    raise ExecutableNotFound(row.name, tuple(tried))


def glob_ambiguity(row: RailRow, fs: RailFileSystem) -> tuple[str, ...]:
    """Every glob match for ``row``, sorted -- a diagnostic, never a gate.

    A second match means the vendor tree holds two builds (two target triples, or a stale
    version left behind by an interrupted npm update). :func:`resolve` deterministically takes
    the first, and this function is how an operator sees that a choice was made at all.
    """
    seen: list[str] = []
    for pattern in row.exe_globs:
        for match in fs.glob(pattern):
            if fs.is_file(match) and match not in seen:
                seen.append(match)
    return tuple(sorted(seen))


def _fallback_warning(rail_name: str, candidate: str, globs: tuple[str, ...]) -> str:
    return (
        f"rail {rail_name!r}: no glob matched {list(globs)}; fell back to {candidate!r}. "
        f"The fallback is an npm shim -- it adds a Node process and needs `node` on PATH, so "
        f"prefer repairing the install over relying on it."
    )
