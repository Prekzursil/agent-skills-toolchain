#!/usr/bin/env python3
"""Probe 2: unreachable-list policy and the network-block un-revoke attack.

Mechanically different from probe 1 (which uses a reachable live list):
  * cut the transport after seeding the cache
  * require a durable STALE record readable from a NEW sink object (separate process-shape)
  * known-revoked still REFUSE
  * unsigned empty list, untrusted-signed empty list, and lower-sequence empty list
    must not un-revoke
  * freshness-window expiry independently emits STALE while still refusing known-revoked
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import (  # noqa: E402
    EVIL,
    SAFE,
    census_payloads,
    dumps_list,
    install,
    list_body,
    make_client,
    serve_signed,
    sign_list,
)
from tools.marketplace.revocation_list.degrade import DegradeSink, STALE  # noqa: E402
from tools.marketplace.revocation_list.fixtures.harness import (  # noqa: E402
    FakeClock,
    StaticTransport,
)
from tools.marketplace.revocation_list.install_gate import InstallRequest  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0079-probe2 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0079-p2-") as tmp:
        root = Path(tmp)
        dest = root / "dest"
        transport = StaticTransport()
        clock = FakeClock()
        client, sink, clock = make_client(root, transport, clock)
        serve_signed(transport, list_body(sequence=4))

        seed = install(client, SAFE, dest)
        if not seed.placed:
            return fail("seed non-revoked install failed on live list")

        # --- unreachable -----------------------------------------------------
        transport.payload = None
        sink.path.unlink(missing_ok=True)
        unreachable_evil = install(client, EVIL, dest)
        unreachable_safe = install(
            client, InstallRequest("pkg.safe", "1.1.0", "key-ok", b"v11"), dest
        )
        later = DegradeSink(sink.path)  # new object, same file: durability
        if unreachable_evil.placed:
            return fail("known-revoked installed while list unreachable")
        if unreachable_evil.decision.action != "REFUSE":
            return fail("known-revoked was not REFUSE under unreachable list")
        if unreachable_evil.decision.list_state != "UNREACHABLE":
            return fail(f"list_state={unreachable_evil.decision.list_state}")
        if not unreachable_safe.placed:
            return fail("non-known-revoked should ALLOW with STALE, not hard-fail")
        if STALE not in unreachable_safe.decision.warnings:
            return fail("STALE missing from decision.warnings")
        if not later.has_stale():
            return fail("STALE did not survive to a later sink reader (silence)")

        # --- unsigned empty list cannot un-revoke ----------------------------
        empty_body = list_body(sequence=99, keys=[], versions=[])
        transport.payload = dumps_list(empty_body)
        unsigned_evil = install(client, EVIL, dest)
        if unsigned_evil.placed or not unsigned_evil.decision.known_revoked:
            return fail("unsigned empty list un-revoked a cached entry")

        # --- untrusted signature cannot un-revoke ----------------------------
        transport.payload = dumps_list(sign_list(empty_body, signer="untrusted"))
        forged_evil = install(client, EVIL, dest)
        if forged_evil.placed or not forged_evil.decision.known_revoked:
            return fail("untrusted-signed empty list un-revoked a cached entry")

        # --- lower sequence cannot roll back ---------------------------------
        transport.payload = dumps_list(
            sign_list(list_body(sequence=1, keys=[], versions=[]))
        )
        rollback_evil = install(client, EVIL, dest)
        if rollback_evil.placed:
            return fail("lower-sequence list un-revoked a cached entry")

        # --- freshness window ------------------------------------------------
        dest2 = root / "dest-fresh"
        transport2 = StaticTransport()
        clock2 = FakeClock()
        client2, sink2, _ = make_client(root / "fresh", transport2, clock2)
        serve_signed(
            transport2, list_body(sequence=2, expires_at="2026-08-24T00:00:00Z")
        )
        stale_evil = install(client2, EVIL, dest2)
        stale_safe = install(client2, SAFE, dest2)
        if stale_evil.placed:
            return fail("expired list allowed a revoked version")
        if stale_evil.decision.list_state != "STALE":
            return fail(f"expired list_state={stale_evil.decision.list_state}")
        if not stale_safe.placed:
            return fail("expired list blocked the negative control")
        if not sink2.has_stale():
            return fail("expired list was silent (no STALE)")

        report = {
            "probe": "probe2-unreachable-policy",
            "unit_id": "IMP-0079",
            "unreachable_evil_refused": not unreachable_evil.placed,
            "unreachable_safe_allowed_with_stale": unreachable_safe.placed
            and later.has_stale(),
            "stale_durable_in_later_reader": later.has_stale(),
            "unsigned_empty_did_not_unrevoke": not unsigned_evil.placed,
            "untrusted_empty_did_not_unrevoke": not forged_evil.placed,
            "lower_sequence_did_not_unrevoke": not rollback_evil.placed,
            "freshness_window_stale": sink2.has_stale()
            and stale_evil.decision.list_state == "STALE",
            "census_unreachable_tree": census_payloads(dest),
        }
        print(json.dumps(report, indent=1))
        expected_census = [
            "pkg.safe/1.0.0/payload.bin",
            "pkg.safe/1.1.0/payload.bin",
        ]
        if census_payloads(dest) != expected_census:
            return fail(f"census={census_payloads(dest)}")

    print(
        "unreachable_STALE=True known_revoked_refused=True "
        "network_block_cannot_unrevoke=True freshness_window=True"
    )
    print("SUCCESS:IMP-0079-probe2 unreachable policy; no silent un-revoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
