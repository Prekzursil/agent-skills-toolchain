"""Immutable, redaction-safe snapshots of consumer OAuth credentials.

This module reads credentials; it never refreshes or writes them.  Secret values
are retained only by an opaque handle whose representation is always redacted.
"""

from __future__ import annotations

import base64
import json
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


def _b64url_json(value: str) -> dict[str, Any] | None:
    try:
        parts = value.split(".")
        if len(parts) != 3:
            return None
        raw = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


class CredentialHandle:
    """Opaque bearer credentials for internal HTTP-header construction only."""

    __slots__ = ("__access_token", "__account_id")

    def __init__(self, access_token: str, account_id: str) -> None:
        self.__access_token = access_token
        self.__account_id = account_id

    def __repr__(self) -> str:
        return "CredentialHandle(<redacted>)"

    __str__ = __repr__

    def apply_to_headers(self, headers: Mapping[str, str]) -> dict[str, str]:
        """Return a copy with the private authentication headers applied."""
        result = dict(headers)
        result["Authorization"] = f"Bearer {self.__access_token}"
        result["ChatGPT-Account-Id"] = self.__account_id
        return result


@dataclass(frozen=True)
class CredentialSnapshot:
    """Immutable auth-file metadata plus a deliberately opaque secret handle."""

    path: Path
    mtime_ns: int
    file_mode: int
    auth_mode: str | None
    last_refresh: str | None
    access_token_present: bool
    account_id_present: bool
    exp_utc: str | None
    expires_at_epoch: int | None
    expired: bool | None
    within_5min_of_exp: bool | None
    _handle: CredentialHandle = field(repr=False, compare=False)

    @property
    def credentials(self) -> CredentialHandle:
        """Return the opaque internal handle; callers cannot inspect its values."""
        return self._handle

    def public_status(self) -> dict[str, Any]:
        """Return metadata safe for status endpoints and logs."""
        return {
            "path": str(self.path),
            "mtime_ns": self.mtime_ns,
            "file_mode": f"{self.file_mode:04o}",
            "auth_mode": self.auth_mode,
            "last_refresh": self.last_refresh,
            "access_token_present": self.access_token_present,
            "account_id_present": self.account_id_present,
            "exp_utc": self.exp_utc,
            "expires_at_epoch": self.expires_at_epoch,
            "expired": self.expired,
            "within_5min_of_exp": self.within_5min_of_exp,
        }


def load_from_auth_json(path: Path | str) -> CredentialSnapshot:
    """Load a stable auth.json image without exposing credential values.

    A concurrent atomic replacement is detected by comparing file identity and
    metadata before and after the read.  The operation retries briefly and fails
    closed if the file keeps changing.
    """
    auth_path = Path(path)
    raw: str | None = None
    stable_stat = None
    for _ in range(3):
        before = auth_path.stat()
        raw = auth_path.read_text(encoding="utf-8")
        after = auth_path.stat()
        if (
            before.st_dev == after.st_dev
            and before.st_ino == after.st_ino
            and before.st_mtime_ns == after.st_mtime_ns
            and before.st_size == after.st_size
        ):
            stable_stat = after
            break
    if raw is None or stable_stat is None:
        raise RuntimeError("auth.json changed repeatedly while loading")

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("auth.json root must be an object")
    tokens = data.get("tokens") or {}
    if not isinstance(tokens, dict):
        raise ValueError("auth.json tokens must be an object")
    access = tokens.get("access_token")
    if not isinstance(access, str) or not access:
        raise RuntimeError("no access_token in auth.json")

    claims = _b64url_json(access) or {}
    oauth_claims = claims.get("https://api.openai.com/auth") or {}
    if not isinstance(oauth_claims, dict):
        oauth_claims = {}
    account_id = oauth_claims.get("chatgpt_account_id") or tokens.get("account_id") or ""
    if not isinstance(account_id, str):
        account_id = str(account_id)

    exp_value = claims.get("exp")
    exp: int | None
    try:
        exp = int(exp_value) if exp_value is not None else None
    except (TypeError, ValueError, OverflowError):
        exp = None
    now = datetime.now(timezone.utc)
    try:
        exp_time = datetime.fromtimestamp(exp, timezone.utc) if exp is not None else None
    except (OverflowError, OSError, ValueError):
        exp = None
        exp_time = None

    auth_mode = data.get("auth_mode")
    last_refresh = data.get("last_refresh")
    return CredentialSnapshot(
        path=auth_path,
        mtime_ns=stable_stat.st_mtime_ns,
        file_mode=stat.S_IMODE(stable_stat.st_mode),
        auth_mode=str(auth_mode) if auth_mode is not None else None,
        last_refresh=str(last_refresh) if last_refresh is not None else None,
        access_token_present=True,
        account_id_present=bool(account_id),
        exp_utc=exp_time.isoformat() if exp_time else None,
        expires_at_epoch=exp,
        expired=exp_time <= now if exp_time else None,
        within_5min_of_exp=(exp_time - now).total_seconds() <= 300 if exp_time else None,
        _handle=CredentialHandle(access, account_id),
    )


def is_stale_mtime(path: Path | str, known_mtime: int | float | None) -> bool:
    """Return whether the auth file differs from a known mtime.

    Integer values are interpreted as nanoseconds (``st_mtime_ns``); float
    values preserve compatibility with callers storing ``st_mtime`` seconds.
    Missing or inaccessible files are stale so consumers fail closed on reload.
    """
    if known_mtime is None:
        return True
    try:
        current = Path(path).stat()
    except OSError:
        return True
    if isinstance(known_mtime, int):
        return current.st_mtime_ns != known_mtime
    return current.st_mtime != known_mtime
