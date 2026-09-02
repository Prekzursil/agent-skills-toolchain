#!/usr/bin/env python3
"""Shared fixture wiring for IMP-0079 named probes."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from load_impl import boot_marketplace  # noqa: E402

boot_marketplace(REPO)

from tools.marketplace.revocation_list.degrade import DegradeSink  # noqa: E402
from tools.marketplace.revocation_list.fixtures.harness import (  # noqa: E402
    FakeClock,
    StaticTransport,
)
from tools.marketplace.revocation_list.fixtures.sign import (  # noqa: E402
    dumps_list,
    owner_public_map,
    sign_list,
)
from tools.marketplace.revocation_list.install_gate import (  # noqa: E402
    InstallRequest,
    census_payloads,
    install,
)
from tools.marketplace.revocation_list.revocation import RevocationClient  # noqa: E402

SAFE = InstallRequest("pkg.safe", "1.0.0", "key-ok", b"safe-payload")
EVIL = InstallRequest("pkg.evil", "1.0.0", "key-ok", b"evil-payload")
COMPROMISED = InstallRequest("pkg.other", "2.0.0", "key-compromised", b"other-payload")


def list_body(
    *,
    sequence: int = 2,
    expires_at: str = "2026-08-25T00:00:00Z",
    keys=None,
    versions=None,
) -> dict:
    return {
        "schema": "marketplace.revocation-list/v1",
        "issued_at": "2026-08-24T00:00:00Z",
        "expires_at": expires_at,
        "sequence": sequence,
        "revoked_keys": keys
        if keys is not None
        else [
            {
                "key_id": "key-compromised",
                "reason": "compromised",
                "revoked_at": "2026-08-24T00:00:00Z",
            }
        ],
        "revoked_versions": versions
        if versions is not None
        else [{"package_id": "pkg.evil", "version": "1.0.0", "reason": "withdrawn"}],
    }


def make_client(root: Path, transport: StaticTransport, clock: FakeClock | None = None):
    clock = clock or FakeClock()
    sink = DegradeSink(root / "degrade.json", clock=clock)
    client = RevocationClient(
        transport=transport,
        cache_path=root / "cache.json",
        owner_public_keys=owner_public_map(),
        degrade=sink,
        clock=clock,
        backoff=(0.0, 0.0, 0.0),
        sleep=lambda _d: None,
    )
    return client, sink, clock


def serve_signed(transport: StaticTransport, body: dict | None = None, **sign_kw) -> bytes:
    raw = dumps_list(sign_list(body if body is not None else list_body(), **sign_kw))
    transport.payload = raw
    return raw
