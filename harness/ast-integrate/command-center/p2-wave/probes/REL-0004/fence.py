"""Owner-profile fence: the canary HOME must never be the live owner profile."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


class IsolationError(RuntimeError):
    """Canary HOME resolved to the owner's live profile."""


def _resolve_existing(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except OSError:
        return path.expanduser().absolute()


@dataclass(frozen=True)
class OwnerFence:
    """Snapshot of the invoking user's real home(s), taken before HOME is mutated."""

    owner_homes: tuple[Path, ...]

    @classmethod
    def capture(cls) -> "OwnerFence":
        homes: list[Path] = []
        for raw in (
            os.environ.get("HOME"),
            os.environ.get("USERPROFILE"),
            str(Path.home()),
        ):
            if raw:
                homes.append(_resolve_existing(Path(raw)))
        try:
            import pwd

            homes.append(_resolve_existing(Path(pwd.getpwuid(os.getuid()).pw_dir)))
        except Exception:
            pass
        unique: list[Path] = []
        seen: set[str] = set()
        for home in homes:
            key = str(home)
            if key not in seen:
                seen.add(key)
                unique.append(home)
        if not unique:
            raise IsolationError("ISOLATION-VIOLATION: could not capture owner home")
        return cls(tuple(unique))

    @property
    def primary(self) -> Path:
        return self.owner_homes[0]

    def is_forbidden(self, path: Path) -> bool:
        resolved = _resolve_existing(path)
        for home in self.owner_homes:
            if resolved == home:
                return True
            if home in resolved.parents:
                return True
        return False

    def assert_throwaway(self, profile: Path) -> Path:
        resolved = _resolve_existing(profile)
        if self.is_forbidden(resolved):
            raise IsolationError(
                "ISOLATION-VIOLATION: canary HOME resolves to the owner's live "
                f"profile: profile={resolved} owner_homes={[str(h) for h in self.owner_homes]}"
            )
        return resolved
