#!/usr/bin/env python3
"""Probe 2: throwaway identity ACL + file-lease listing.

Mechanically different from probe 1: this does not classify payload
sensitivity. It registers a third identity, fetches the victim inbox by
name (published optional-token tool), lists file reservations, then
deregisters the throwaway. Existing identities are left untouched.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import dumps, measure_probe2  # noqa: E402


def main() -> int:
    doc = measure_probe2()
    print(dumps(doc))
    peer = doc["optional_token_fetch_inbox_victim"]
    print(
        "own_ok={0} peer_read={1} lease={2} retired={3} unmodified={4}".format(
            doc.get("own_fetch_ok"),
            peer.get("sees_sensitive_peer_mail"),
            doc.get("throwaway_sees_victim_lease_abspath"),
            doc.get("throwaway_retired"),
            doc.get("existing_identities_unmodified"),
        )
    )
    if not doc.get("pass"):
        print("FAILED:ADV-0043-probe2 throwaway ACL probe did not hold")
        return 1
    print("SUCCESS:ADV-0043-probe2 throwaway identity ACL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
