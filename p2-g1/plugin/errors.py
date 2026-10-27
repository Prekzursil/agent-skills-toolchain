"""Plugin install errors."""
from __future__ import annotations


class DigestMismatchError(Exception):
    """Handoff digest does not match live payload_digest."""


class InstallError(Exception):
    """Install refused."""
