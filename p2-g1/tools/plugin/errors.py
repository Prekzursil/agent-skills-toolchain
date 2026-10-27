"""Plugin install errors."""
from __future__ import annotations


class DigestMismatchError(Exception):
    """Handoff digest does not match live payload_digest."""


class InstallError(Exception):
    """Install refused."""


class MissingTransactionIdError(InstallError):
    """Handoff is untyped or missing transaction_id."""


class PermissionWideningBlocked(InstallError):
    """Candidate permissions strictly widen the installed set."""


class ProjectionError(InstallError):
    """Projection dest escapes dest_root or census mismatches."""


class MissingTransactionIdError(InstallError):
    """Handoff lacked a transaction id; no files may be placed."""


class PermissionWideningBlocked(InstallError):
    """Candidate permissions are a strict widening of the installed set."""

    def __init__(self, added, *, installed=None, candidate=None, rendered_diff: str | None = None):
        self.added = list(added)
        self.installed = list(installed or [])
        self.candidate = list(candidate or [])
        self.status = "blocked"
        self.halt = True
        self.warn = False
        self.rendered_diff = rendered_diff or ("added permissions: " + ", ".join(self.added))
        super().__init__(self.rendered_diff + " " + " ".join(self.added))
