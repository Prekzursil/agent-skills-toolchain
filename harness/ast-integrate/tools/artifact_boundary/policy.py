"""Trusted policy object handed to apply_policy. Never a payload."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustedPolicy:
    name: str = "deny-untrusted-body"
    allow_credential_read: bool = False
    role: str = "consumer"
    default_verdict: str = "HOLD"
