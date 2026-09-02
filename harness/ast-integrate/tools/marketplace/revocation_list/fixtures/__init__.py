"""Test doubles and owner-signing helpers for the revocation-list gate (IMP-0079).

Explicit re-exports only; the implementations live in :mod:`.harness`
(:class:`StaticTransport`, :class:`FakeClock`) and :mod:`.sign`
(deterministic owner / untrusted Ed25519 signers).
"""
from __future__ import annotations

from .harness import DEFAULT_CLOCK_START, STATIC_URL, FakeClock, StaticTransport
from .sign import (
    OWNER_KEY_ID,
    SIGNERS,
    UNTRUSTED_KEY_ID,
    dumps_list,
    owner_public_map,
    private_key_for,
    public_key_hex,
    seed_for,
    sign_list,
    tampered_list,
)

__all__ = [
    "DEFAULT_CLOCK_START",
    "FakeClock",
    "OWNER_KEY_ID",
    "SIGNERS",
    "STATIC_URL",
    "StaticTransport",
    "UNTRUSTED_KEY_ID",
    "dumps_list",
    "owner_public_map",
    "private_key_for",
    "public_key_hex",
    "seed_for",
    "sign_list",
    "tampered_list",
]
