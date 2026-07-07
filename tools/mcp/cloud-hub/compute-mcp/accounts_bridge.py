#!/usr/bin/env python3
"""Credential resolution for the compute layer, reusing the hub's account store.

The compute server dispatches DIRECTLY to provider APIs, so it must resolve the
same per-account credentials the cloud-hub injects when it spawns the RunPod /
OVH / Lightning backends. Rather than duplicate that policy, this bridge builds
an :class:`accounts.AccountStore` from the three relevant backend policies
(pulled from ``backends.default_backends()``) and reads the ACTIVE account's env
through its public ``active_env``.

Named-account resolution (``account="work"``) needs a per-name lookup the store
does not expose publicly, so -- to avoid editing the shared ``accounts.py`` -- we
replicate its ~10-line seed+resolve here: read the gitignored ``accounts.json``
record (or synthesize a seed from the platform's registration env) and resolve
that account's ``${ENV}`` bundle with the public ``accounts.resolve_env``.

A per-provider base of known env vars (OVH's endpoint + OAuth2 vars, which are
not in ``seed_env``) is layered UNDER the account bundle so a seeded default
still carries everything the adapter needs.
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_HUB = os.path.dirname(_HERE)  # tools/mcp/cloud-hub
_SHARED = os.path.join(os.path.dirname(_HUB), "_shared")  # tools/mcp/_shared
for _p in (_HUB, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import accounts  # noqa: E402
from backends import default_backends  # noqa: E402

COMPUTE_PLATFORMS = ("runpod", "ovh", "lightning")
ACCOUNTS_PATH = os.path.join(_HUB, "accounts.json")

# Env vars each adapter may read that are NOT necessarily in the platform's
# ``seed_env`` (OVH carries its endpoint + OAuth2 creds + project in the account
# bundle). Layered under the resolved account env so seeded defaults still work.
_PROVIDER_ENV = {
    "runpod": ("RUNPOD_API_KEY",),
    "ovh": (
        "OVH_ENDPOINT",
        "OVH_APPLICATION_KEY",
        "OVH_APPLICATION_SECRET",
        "OVH_CONSUMER_KEY",
        "OVH_CLIENT_ID",
        "OVH_CLIENT_SECRET",
        "OVH_CLOUD_PROJECT_ID",
    ),
    "lightning": ("LIGHTNING_USER_ID", "LIGHTNING_API_KEY"),
}


class ComputeAccounts:
    """Resolve a compute provider's credentials (active or a named account)."""

    def __init__(self, accounts_path, policies, environ=None) -> None:
        self._environ = dict(environ) if environ is not None else dict(os.environ)
        self._policies = {p.platform: p for p in policies}
        self._store = accounts.AccountStore(
            accounts_path, policies, environ=self._environ
        )

    def resolve_env(self, provider: str, account: str = "") -> dict[str, str]:
        """Env dict for ``provider``'s active (or named) account, or ``{}``."""
        base = {
            k: self._environ[k]
            for k in _PROVIDER_ENV.get(provider, ())
            if k in self._environ
        }
        base.update(self._account_env(provider, account))
        return base

    def _account_env(self, provider: str, account: str) -> dict[str, str]:
        pol = self._policies.get(provider)
        if pol is None:
            return {}
        if not account:
            return self._store.active_env(provider)
        for acct in self._record(pol).get("accounts", []):
            if acct.get("name") == account:
                return accounts.resolve_env(acct.get("env", {}), self._environ)
        return {}

    def _record(self, pol) -> dict:
        """Stored record for a named lookup, else a seeded default (local)."""
        try:
            with open(self._store.path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            rec = data.get(pol.platform) if isinstance(data, dict) else None
            if rec and rec.get("accounts"):
                return rec
        except (OSError, json.JSONDecodeError):
            pass
        if pol.seed_env and all(n in self._environ for n in pol.seed_env):
            return {
                "active": "default",
                "accounts": [
                    {"name": "default", "env": {n: f"${{{n}}}" for n in pol.seed_env}}
                ],
            }
        return {"active": None, "accounts": []}


def build(accounts_path: str = "", environ=None) -> ComputeAccounts:
    """Construct a ComputeAccounts over the runpod/ovh/lightning policies."""
    by_id = {s.id: s for s in default_backends()}
    policies = [
        by_id[i].account
        for i in COMPUTE_PLATFORMS
        if i in by_id and by_id[i].account is not None
    ]
    return ComputeAccounts(accounts_path or ACCOUNTS_PATH, policies, environ=environ)
