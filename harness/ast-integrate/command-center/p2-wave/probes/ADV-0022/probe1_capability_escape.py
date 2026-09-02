#!/usr/bin/env python3
"""Probe 1: narrow-declared component attempts spawn, loopback, write, sibling.

Exit 0 only when controls fire: disposable sandbox, loopback-only network,
wide-declared control unimpeded, ARC-0081 interceptor denies the same four
requests for the narrow set. Product mismatches are findings, not probe
failures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from common import ATTEMPTS, UNIT, dump_json  # noqa: E402
from mechanism import measure  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def main() -> int:
    live = measure()
    payload = {
        "ok": True,
        "narrow_attempts": live["narrow"]["attempts"],
        "narrow_observed": live["narrow"]["observed"],
        "control_unimpeded": live["control_unimpeded"],
        "narrow_escaped": live["narrow_escaped"],
        "interceptor_denies_narrow": live["interceptor_denies_narrow"],
        "interceptor_allows_wide": live["interceptor_allows_wide"],
        "loopback_only": live["loopback_only"],
        "third_party_contacted": live["third_party_contacted"],
        "live_credential_used": live["live_credential_used"],
        "choke_point_wired_into_host": live["choke_point_wired_into_host"],
    }
    print(dump_json(payload), end="")
    if live["third_party_contacted"] or live["live_credential_used"]:
        return fail("probe contacted a third-party system or used a live credential")
    if not live["loopback_only"]:
        return fail("network attempt was not loopback-only")
    if not live["control_unimpeded"]:
        return fail("wide-declared control did not run unimpeded")
    if not live["interceptor_denies_narrow"]:
        return fail("ARC-0081 interceptor did not DENY all four narrow requests")
    if not live["interceptor_allows_wide"]:
        return fail("ARC-0081 interceptor did not GRANT the wide control requests")
    if live["narrow"]["host"]["exit_code"] not in (0, None):
        # Component crash is a finding only if no attempt ran; require attempted.
        attempted = all(a["attempted"] for a in live["narrow"]["attempts"])
        if not attempted:
            return fail("narrow component did not attempt the four actions")
    missing = [a for a in ATTEMPTS if a not in live["narrow"]["observed"]]
    if missing:
        return fail(f"missing observed keys {missing}")
    print(f"SUCCESS:{UNIT}-probe1 capability-escape checkable run recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
