#!/usr/bin/env python3
"""Per-key health + reactive rotate-retry for the search-hub multiplexer.

This is the brain of the rotator, kept free of any child-process / socket I/O so
it is fully unit-testable: the hub injects a ``forward(name, request) -> response``
callback (a synchronous send-to-that-key's-child), and everything else -- which
key is active, when to rotate, how long to cool an exhausted key -- is decided
here as a pure function of the AccountStore roster + accumulated key health.

Policy (locked in the grill):

* SG-2 reactive: route each call to the active key's child; on a HARD exhaustion
  response, cool that key and retry the SAME call once on the next non-cooled
  key. If none remain, return the provider's native error unchanged.
* SG-3 keys: true exhaustion (paid keys) cools LONG -- until the billing period
  resets (seconds to the next UTC month boundary, or a ``SEARCH_HUB_EXHAUST_
  COOLDOWN_S`` override). A 429 rate-limit does NOT cool the key; the native
  error (carrying Retry-After) is returned so the caller backs off.
* Auto-rotation NEVER mutates the store's active pointer (no global respawn-flip
  that would yank concurrent calls); manual ``*_account_switch``/``cycle`` remain
  the only deliberate active-key changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import time as _now
from typing import Callable, Iterable, Mapping

import providers
import usage

# forward(name, request) -> the child's JSON-RPC response dict for that key.
Forward = Callable[[str, dict], dict]


def seconds_until_month_reset(now_epoch: float) -> float:
    """Seconds from ``now`` to 00:00 UTC on the 1st of next month (billing reset)."""
    dt = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    year, month = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
    nxt = datetime(year, month, 1, tzinfo=timezone.utc)
    return max(0.0, (nxt - dt).total_seconds())


@dataclass
class KeyHealth:
    """Mutable per-key health record (cooldown + last observed reason)."""

    cooldown_until: float = 0.0
    last_checked: float = 0.0
    last_reason: str = ""
    exhausted_count: int = 0


@dataclass
class Rotator:
    """Chooses the active key per provider and applies the rotate-retry policy."""

    specs: Mapping[str, providers.ProviderSpec]
    store: object  # accounts.AccountStore (duck-typed: handle + env_for)
    environ: Mapping[str, str] = field(default_factory=lambda: os.environ)
    clock: Callable[[], float] = _now
    getter: usage.Getter | None = None  # usage-probe HTTP getter (injected in tests)
    _health: dict = field(default_factory=dict)  # (platform, name) -> KeyHealth

    @classmethod
    def from_specs(
        cls, specs: Iterable[providers.ProviderSpec], store, **kw
    ) -> "Rotator":
        return cls(specs={s.platform: s for s in specs}, store=store, **kw)

    # ---- key roster -----------------------------------------------------
    def key_names(self, platform: str) -> list[str]:
        """All account (key) names for a provider, in round-robin order."""
        listing = self.store.handle(platform, "list", {})
        return list(listing.get("accounts") or [])

    def usable_names(self, platform: str) -> list[str]:
        """Key names whose API secret actually resolves (skip stale empty refs)."""
        return [n for n in self.key_names(platform) if self._has_secret(platform, n)]

    def _has_secret(self, platform: str, name: str) -> bool:
        return bool(self.key_value(platform, name))

    def key_value(self, platform: str, name: str) -> str:
        """The resolved API-key string for a named key (for usage probes)."""
        spec = self.specs[platform]
        return self.store.env_for(platform, name).get(spec.key_env, "")

    # ---- health ---------------------------------------------------------
    def _rec(self, platform: str, name: str) -> KeyHealth:
        return self._health.setdefault((platform, name), KeyHealth())

    def is_cooled(self, platform: str, name: str) -> bool:
        rec = self._health.get((platform, name))
        return bool(rec and rec.cooldown_until > self.clock())

    def mark_exhausted(
        self, platform: str, name: str, cooldown_s: float, reason: str = "exhausted"
    ) -> None:
        rec = self._rec(platform, name)
        now = self.clock()
        rec.cooldown_until = now + cooldown_s
        rec.last_checked = now
        rec.last_reason = reason
        rec.exhausted_count += 1

    def mark_rate_limited(
        self, platform: str, name: str, retry_after: int | None = None
    ) -> None:
        """Record a 429 WITHOUT cooling the key (SG-3: honour Retry-After only)."""
        rec = self._rec(platform, name)
        rec.last_checked = self.clock()
        rec.last_reason = f"rate_limited(retry_after={retry_after})"

    def clear_cooldown(self, platform: str, name: str) -> None:
        """Drop a key's cooldown (a deliberate manual switch/cycle overrides it)."""
        self._health.pop((platform, name), None)

    def exhaust_cooldown_s(self) -> float:
        """Long cooldown for a truly exhausted paid key (until billing reset)."""
        override = self.environ.get("SEARCH_HUB_EXHAUST_COOLDOWN_S")
        if override:
            try:
                return max(0.0, float(override))
            except ValueError:
                pass
        return seconds_until_month_reset(self.clock())

    # ---- selection ------------------------------------------------------
    def pick_active(self, platform: str) -> str | None:
        """The key to route to now: the store's active key if healthy, else the
        next non-cooled key round-robin. None if every usable key is cooled."""
        names = self.usable_names(platform)
        if not names:
            return None
        healthy = [n for n in names if not self.is_cooled(platform, n)]
        if not healthy:
            return None
        active = self.store.handle(platform, "current", {}).get("active")
        if active in healthy:
            return active
        start = names.index(active) if active in names else -1
        for step in range(1, len(names) + 1):
            cand = names[(start + step) % len(names)]
            if cand in healthy:
                return cand
        return healthy[0]

    # ---- classification -------------------------------------------------
    def resolve_signal(
        self, platform: str, name: str, response: dict
    ) -> tuple[str, int | None]:
        """Classify a child response; resolve Tavily's AMBIGUOUS 429 via /usage."""
        spec = self.specs[platform]
        signal, retry_after = providers.classify(spec, response)
        if signal == providers.AMBIGUOUS:
            signal = self._resolve_ambiguous(platform, name)
        return signal, retry_after

    def _resolve_ambiguous(self, platform: str, name: str) -> str:
        """Tavily 429: probe /usage -- no headroom => EXHAUSTED, else RATE_LIMITED."""
        spec = self.specs[platform]
        report = usage.usage_for(
            spec.usage_kind, self.key_value(platform, name), name, self.getter
        )
        remaining = report.get("remaining")
        if (
            report.get("ok")
            and isinstance(remaining, (int, float))
            and not isinstance(remaining, bool)
            and remaining <= 0
        ):
            return providers.EXHAUSTED
        return providers.RATE_LIMITED

    # ---- the per-call rotate-retry wrapper ------------------------------
    def route_call(self, platform: str, request: dict, forward: Forward) -> dict:
        """Route one tools/call through the active key; rotate+retry once on
        hard-exhaustion. ``forward(name, request)`` synchronously sends to that
        key's child and returns its JSON-RPC response dict."""
        name = self.pick_active(platform)
        if name is None:
            return self._exhausted_reply(platform, request)
        response = forward(name, request)
        signal, retry_after = self.resolve_signal(platform, name, response)
        if signal == providers.EXHAUSTED:
            self.mark_exhausted(
                platform, name, self.exhaust_cooldown_s(), "hard-exhaustion"
            )
            nxt = self.pick_active(platform)
            if nxt is not None and nxt != name:
                return forward(nxt, request)  # retry the SAME call once
            return response  # all cooled -> the provider's native error, verbatim
        if signal == providers.RATE_LIMITED:
            self.mark_rate_limited(platform, name, retry_after)
        return response

    def _exhausted_reply(self, platform: str, request: dict) -> dict:
        """Synthesize an MCP isError result when there is no key to route to."""
        spec = self.specs[platform]
        if not self.usable_names(platform):
            text = (
                f"[search-hub] no usable {spec.label} API key: set {spec.key_env} "
                f"(and optional {spec.key_env}_2.. backups) or add one via "
                f"{spec.prefix}_account_add."
            )
        else:
            text = (
                f"[search-hub] all {spec.label} keys are cooling after "
                f"hard-exhaustion; they reset at the billing period. Check "
                f"{spec.prefix}_account_list / search_usage, add another key, "
                f"or wait for the cooldown to lapse."
            )
        return {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"content": [{"type": "text", "text": text}], "isError": True},
        }

    # ---- observability --------------------------------------------------
    def health_snapshot(self, platform: str) -> list[dict]:
        """Per-key health for the on-demand usage/status tool."""
        now = self.clock()
        out: list[dict] = []
        for name in self.key_names(platform):
            rec = self._health.get((platform, name))
            cooled = bool(rec and rec.cooldown_until > now)
            out.append(
                {
                    "name": name,
                    "usable": self._has_secret(platform, name),
                    "cooled": cooled,
                    "cooldown_remaining_s": (
                        round(rec.cooldown_until - now, 1) if cooled else 0
                    ),
                    "last_reason": rec.last_reason if rec else "",
                }
            )
        return out


def seed_backup_keys(
    store, specs: Iterable[providers.ProviderSpec], environ: Mapping[str, str]
) -> list[dict]:
    """Register numbered backup keys (KEY_2..KEY_N) as ${ENV}-ref accounts.

    Plug-and-play multi-key: exporting ``EXA_API_KEY_2`` (etc.) turns it into an
    extra rotation key with ZERO manual ``*_account_add`` calls. Stored as a
    ``${ENV}`` REFERENCE (never the literal secret, matching accounts.py seeding)
    and idempotent, so repeated hub starts don't duplicate. Returns what it added.
    """
    added: list[dict] = []
    for spec in specs:
        existing = set(store.handle(spec.platform, "list", {}).get("accounts") or [])
        for n in range(2, spec.max_backup_keys + 1):
            var = f"{spec.key_env}_{n}"
            name = f"key{n}"
            value = environ.get(var, "")
            if not value.strip() or name in existing:
                continue
            res = store.handle(
                spec.platform,
                "add",
                {
                    "name": name,
                    "env": {spec.key_env: f"${{{var}}}"},
                    "label": f"{spec.key_env}_{n}",
                },
            )
            if res.get("ok"):
                added.append({"platform": spec.platform, "name": name, "env_var": var})
    return added
