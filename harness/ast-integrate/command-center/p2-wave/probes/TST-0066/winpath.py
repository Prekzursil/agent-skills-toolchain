"""Windows path-identity model used by TST-0066.

Linux does not strip trailing dots/spaces or expose 8.3 names. The unit's
question is about Win32 identity, so the probe applies the documented
normalisation rather than trusting the host filesystem.

Order matches CreateFile (no \\\\?\\ prefix):
  1. fold separators to backslash
  2. strip trailing spaces and periods from each component (not '.' / '..')
  3. expand 8.3 names through the fixture volume map
  4. collapse '.' and '..'
  5. casefold (NTFS default)

The volume map is explicit. A guessed 8.3 generator would invent names the
probe could not show equal a real directory entry.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Volume:
    """Bidirectional long <-> 8.3 map for one modelled NTFS tree."""

    long_to_short: dict[str, str]

    def short_to_long(self) -> dict[str, str]:
        return {s.upper(): long_name for long_name, s in self.long_to_short.items()}


# Fixture volume for the two catalog examples: trailing-dot `hook.py.` and
# PROGRA~1 vs "Program Files", plus the repo-root containment tree.
FIXTURE_VOLUME = Volume(
    long_to_short={
        "Program Files": "PROGRA~1",
        "ast-integrate": "AST-IN~1",
        "command-center": "COMMAN~1",
        "WORK-UNIT-CATALOG.json": "WORK-U~1.JSO",
        "secret.txt": "SECRET~1.TXT",
        "hook.py": "HOOK~1.PY",
        "hooks": "HOOKS~1",
        "app": "APP~1",
        "work": "WORK~1",
    }
)


def split_drive(path: str) -> tuple[str, str]:
    raw = (path or "").replace("/", "\\")
    if len(raw) >= 2 and raw[1] == ":" and raw[0].isalpha():
        return raw[:2].upper(), raw[2:].lstrip("\\")
    return "", raw.lstrip("\\")


def strip_win_component(part: str) -> str:
    if part in {"", ".", ".."}:
        return part
    return part.rstrip(" .")


def expand_short_component(part: str, volume: Volume) -> str:
    if not part or part in {".", ".."}:
        return part
    mapped = volume.short_to_long().get(part.upper())
    return mapped if mapped else part


def win_identity(path: str, volume: Volume | None = None) -> str:
    """Canonical Windows identity string (drive + casefolded backslash path)."""
    vol = volume or FIXTURE_VOLUME
    drive, rest = split_drive(path)
    parts: list[str] = []
    for raw in rest.split("\\"):
        if raw == "":
            continue
        stripped = strip_win_component(raw)
        if stripped == "":
            continue
        expanded = expand_short_component(stripped, vol)
        if expanded == ".":
            continue
        if expanded == "..":
            if parts:
                parts.pop()
            continue
        parts.append(expanded)
    body = "\\".join(parts).casefold()
    if drive:
        return f"{drive.casefold()}\\{body}" if body else drive.casefold() + "\\"
    return body


def same_identity(a: str, b: str, volume: Volume | None = None) -> bool:
    return win_identity(a, volume) == win_identity(b, volume)


def sep_fold(path: str) -> str:
    return (path or "").replace("\\", "/")


def is_8_3_token(part: str) -> bool:
    """True when a component looks like a generated 8.3 name (contains ~)."""
    if not part or part in {".", ".."}:
        return False
    return "~" in part
