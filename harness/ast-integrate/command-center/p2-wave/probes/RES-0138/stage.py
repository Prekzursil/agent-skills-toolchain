#!/usr/bin/env python3
"""Executable reference kernel for the RES-0138 onion-research stage.

DRY-RUN only. No sockets, no DNS, no torsocks, no live onion fetch.
A missing transcript refuses enable. Every decision is logged, including
BLOCKED. Prompt text is not consulted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from controls import (
    DEFAULT_OWNER_OPT_IN,
    EGRESS_ALLOWLIST,
    FORBIDDEN_HEADER_NAMES,
    FORBIDDEN_METHODS,
    LAWFUL_PUBLIC_ONION,
    METHOD_ALLOWLIST,
)

LAWFUL_BODY = b"lawful-public-research-fixture-body\n"
LABEL_TOR_DERIVED = "TOR-DERIVED"


class LogSinkRequired(RuntimeError):
    """Capability cannot enable without a mandatory transcript."""


class CredentialStoreSealed(RuntimeError):
    """Sealed empty store: no credential can be retrieved."""


@dataclass
class Decision:
    action: str
    reason: str
    prohibition: str | None = None
    control: str | None = None
    logged: bool = False
    seq: int = 0
    body: bytes | None = None
    label: str | None = None
    host: str = ""
    method: str = ""


class Transcript:
    """Append-only hashed log. Silence on BLOCKED is a gate failure."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        payload["seq"] = len(self.events) + 1
        payload["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload["sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.events.append(payload)
        return payload

    def blocked(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("action") == "BLOCKED"]

    def allowed(self) -> list[dict[str, Any]]:
        return [e for e in self.events if e.get("action") == "ALLOWED"]


class CredentialStore:
    """No-credential store: sealed empty. Lookup cannot succeed."""

    sealed = True

    def lookup(self, name: str) -> bytes:
        raise CredentialStoreSealed(f"sealed-empty:{name}")


class FixtureTransport:
    """In-process fixture. Records attempts; never opens a network resource."""

    def __init__(self) -> None:
        self.attempts: list[tuple[str, str]] = []

    def fetch(self, method: str, url: str) -> bytes:
        self.attempts.append((method, url))
        _scheme, host = _split_url(url)
        if method in METHOD_ALLOWLIST and host == LAWFUL_PUBLIC_ONION:
            return LAWFUL_BODY
        raise RuntimeError(f"fixture-miss:{method}:{host}")


def method_gate(method: str) -> Decision | None:
    m = (method or "").upper()
    if m in METHOD_ALLOWLIST:
        return None
    prohibition = "transact"
    if m in {"RESOLVE", "RESOLVE_PTR"}:
        prohibition = "deanonymise"
    elif m in {"CONNECT", "BIND", "UDP-ASSOCIATE", "TRACE"}:
        prohibition = "access_control_bypass"
    elif m in FORBIDDEN_METHODS:
        prohibition = "transact"
    else:
        prohibition = "transact"
    return Decision(
        action="BLOCKED",
        reason=f"method-not-allowlisted:{m}",
        prohibition=prohibition,
        control="read-only-method-allowlist",
        method=m,
    )


def header_gate(headers: dict[str, str] | None) -> Decision | None:
    for key, value in (headers or {}).items():
        if key.lower() in FORBIDDEN_HEADER_NAMES:
            prohibition = "access_control_bypass"
            if key.lower() == "x-operator-identity":
                prohibition = "deanonymise"
            if key.lower() in {"x-wallet", "x-payment-token"}:
                prohibition = "buy_sell"
            return Decision(
                action="BLOCKED",
                reason=f"forbidden-header:{key.lower()}",
                prohibition=prohibition,
                control="no-credential-store",
            )
        if value and key.lower() == "authorization":
            return Decision(
                action="BLOCKED",
                reason="authorization-header",
                prohibition="access_control_bypass",
                control="no-credential-store",
            )
    return None


def isolation_gate(socks_auth: tuple[str, str] | None) -> Decision | None:
    if socks_auth:
        return Decision(
            action="BLOCKED",
            reason="caller-supplied-socks-auth-rejected",
            prohibition="deanonymise",
            control="isolation-token",
        )
    return None


def credential_lookup(store: CredentialStore, name: str) -> Decision | None:
    try:
        store.lookup(name)
    except CredentialStoreSealed:
        return None
    return Decision(
        action="BLOCKED",
        reason="credential-store-not-sealed",
        prohibition="buy_sell",
        control="no-credential-store",
    )


def _split_url(url: str) -> tuple[str, str]:
    """Split scheme and host without urllib (parsing is not a network call)."""
    raw = url or ""
    if "://" not in raw:
        return "", ""
    scheme, rest = raw.split("://", 1)
    hostport = rest.split("/", 1)[0]
    host = hostport.rsplit("@", 1)[-1]
    if host.startswith("["):
        host = host.strip("[]")
    else:
        host = host.split(":")[0]
    return scheme.lower(), host.lower()


def _onion_host(url: str) -> tuple[str | None, Decision | None]:
    scheme, host = _split_url(url)
    if scheme not in {"http", "https"}:
        return None, Decision(
            action="BLOCKED",
            reason=f"scheme-not-allowlisted:{scheme or 'empty'}",
            prohibition="transact",
            control="egress-allowlist",
        )
    if not host.endswith(".onion"):
        return None, Decision(
            action="BLOCKED",
            reason=f"not-onion-host:{host or 'empty'}",
            prohibition="stolen_data",
            control="egress-allowlist",
        )
    label = host[: -len(".onion")]
    if len(label) != 56 or any(c not in "abcdefghijklmnopqrstuvwxyz234567" for c in label):
        return None, Decision(
            action="BLOCKED",
            reason=f"onion-syntax:{host}",
            prohibition="stolen_data",
            control="egress-allowlist",
        )
    return host, None


def egress_gate(url: str) -> tuple[str, Decision | None]:
    host, err = _onion_host(url)
    if err is not None:
        return "", err
    assert host is not None
    if host not in EGRESS_ALLOWLIST:
        prohibition = "stolen_data"
        if host.endswith(".onion"):
            prohibition = "stolen_data"
        return host, Decision(
            action="BLOCKED",
            reason=f"host-not-allowlisted:{host}",
            prohibition=prohibition,
            control="egress-allowlist",
            host=host,
        )
    return host, None


def transcript_append(transcript: Transcript, decision: Decision) -> Decision:
    event = {
        "action": decision.action,
        "reason": decision.reason,
        "prohibition": decision.prohibition,
        "control": decision.control,
        "host": decision.host,
        "method": decision.method,
        "label": decision.label,
    }
    recorded = transcript.append(event)
    decision.seq = int(recorded.get("seq") or 0)
    decision.logged = any(
        e.get("seq") == decision.seq and e.get("action") == decision.action
        for e in transcript.events
    ) and decision.seq > 0
    return decision


@dataclass
class Stage:
    """Opt-in, sandboxed, fully logged onion research stage (dry-run)."""

    owner_opt_in: bool = DEFAULT_OWNER_OPT_IN
    transcript: Transcript | None = None
    store: CredentialStore = field(default_factory=CredentialStore)
    transport: FixtureTransport = field(default_factory=FixtureTransport)
    isolation_token: str = "session-isolation-not-operator-identity"

    @classmethod
    def enable(
        cls,
        owner_opt_in: bool,
        transcript: Transcript | None,
    ) -> "Stage":
        if transcript is None:
            raise LogSinkRequired("mandatory-transcript-missing")
        return cls(owner_opt_in=owner_opt_in, transcript=transcript)

    def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        socks_auth: tuple[str, str] | None = None,
        want_credential: str | None = None,
    ) -> Decision:
        if self.transcript is None:
            raise LogSinkRequired("mandatory-transcript-missing")
        decision = self._decide(method, url, headers, socks_auth, want_credential)
        transcript_append(self.transcript, decision)
        if decision.action == "ALLOWED":
            decision.body = self.transport.fetch(decision.method, url)
            decision.label = LABEL_TOR_DERIVED
        return decision

    def _decide(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        socks_auth: tuple[str, str] | None,
        want_credential: str | None,
    ) -> Decision:
        m = (method or "").upper()
        if not self.owner_opt_in:
            return Decision(
                action="BLOCKED",
                reason="owner-opt-in-absent",
                prohibition=None,
                control="owner-opt-in-gate",
                method=m,
            )
        blocked = method_gate(m)
        if blocked is not None:
            blocked.method = m
            return blocked
        blocked = header_gate(headers)
        if blocked is not None:
            blocked.method = m
            return blocked
        blocked = isolation_gate(socks_auth)
        if blocked is not None:
            blocked.method = m
            return blocked
        if want_credential:
            # Any attempt to read a credential is fail-closed: the store is
            # sealed, and requesting one is treated as buy/sell or bypass.
            try:
                self.store.lookup(want_credential)
            except CredentialStoreSealed:
                return Decision(
                    action="BLOCKED",
                    reason=f"credential-store-sealed:{want_credential}",
                    prohibition="buy_sell",
                    control="no-credential-store",
                    method=m,
                )
        host, blocked = egress_gate(url)
        if blocked is not None:
            blocked.method = m
            blocked.host = host or blocked.host
            return blocked
        return Decision(
            action="ALLOWED",
            reason="public-read",
            prohibition=None,
            control="read-only-method-allowlist",
            method=m,
            host=host,
            label=LABEL_TOR_DERIVED,
        )
