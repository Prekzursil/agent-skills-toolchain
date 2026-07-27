"""In-memory fakes for agentrail's three ports. NO network, NO process spawn, NO real clock.

``FakeFileSystem.glob`` matches SEGMENT BY SEGMENT, the way :mod:`glob` does, rather than with a
bare :func:`fnmatch.fnmatch` over the whole string. That distinction is load-bearing for the
codex row: ``vendor/*/bin`` must match exactly one directory level, and a whole-string matcher
would happily match across separators and make a broken glob look correct.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
import subprocess
from fnmatch import fnmatchcase

from agentrail.ports import SpawnOutcome


class FakeFileSystem:
    """A dict-backed :class:`~agentrail.ports.RailFileSystem`. Paths use forward slashes."""

    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = dict(files or {})
        self.writes: list[tuple[str, str]] = []

    def glob(self, pattern: str) -> tuple[str, ...]:
        parts = pattern.split("/")
        return tuple(
            sorted(
                path for path in self.files if _segments_match(parts, path.split("/"))
            )
        )

    def is_file(self, path: str) -> bool:
        return path in self.files

    def read_bytes(self, path: str) -> bytes | None:
        return self.files.get(path)

    def write_text(self, path: str, text: str) -> None:
        self.files[path] = text.encode("utf-8")
        self.writes.append((path, text))


def _segments_match(pattern_parts: Sequence[str], path_parts: Sequence[str]) -> bool:
    if len(pattern_parts) != len(path_parts):
        return False
    return all(
        fnmatchcase(actual, expected)
        for expected, actual in zip(pattern_parts, path_parts, strict=True)
    )


@dataclass
class FakeSpawn:
    """A scripted :class:`~agentrail.ports.Spawn` that records every call."""

    outcomes: list[SpawnOutcome] = field(default_factory=list)
    calls: list[dict[str, object]] = field(default_factory=list)

    def __call__(
        self,
        *,
        argv: Sequence[str],
        stdin_payload: str | None,
        timeout_s: int,
        cwd: str | None,
    ) -> SpawnOutcome:
        self.calls.append(
            {
                "argv": tuple(argv),
                "stdin_payload": stdin_payload,
                "timeout_s": timeout_s,
                "cwd": cwd,
            }
        )
        if not self.outcomes:
            return SpawnOutcome(exit_code=0, stdout=b"ok")
        return self.outcomes.pop(0)


def completed(
    *, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    """A REAL :class:`subprocess.CompletedProcess`, which is a plain record and spawns nothing.

    Returning the concrete type rather than a look-alike keeps the injected ``run`` seam
    faithful: the fake hands back exactly what :func:`subprocess.run` would.
    """
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr
    )
