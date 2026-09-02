"""Council builder error types. Paths are interpolated only at runtime."""
from __future__ import annotations


class BuildError(Exception):
    """User-facing build failure. The absolute path is an argument, not a template constant."""

    def __init__(self, path: str, message: str) -> None:
        self.path = str(path)
        self.message = str(message)
        super().__init__(f"build error at {self.path}: {self.message}")


class DigestMismatchError(Exception):
    """Handoff digest does not match live payload_digest."""


class InstallError(Exception):
    """Install refused."""
