"""Tests for declared-versus-exercised permission scan."""
from __future__ import annotations

from tools.marketplace.permission_scan import (
    PERM_ENV,
    PERM_FS_WRITE,
    PERM_SECRETS,
    PERM_SUBPROCESS,
    both_states,
    scan_marketplace,
)

MALICIOUS_UNEXERCISED = {PERM_ENV, PERM_FS_WRITE, PERM_SECRETS, PERM_SUBPROCESS}


def run_all() -> None:
    live = both_states()
    if set(live["malicious_unexercised"]) != MALICIOUS_UNEXERCISED:
        raise AssertionError(live["malicious_unexercised"])
    if not live["pass"]:
        raise AssertionError(live)
    scan = scan_marketplace()
    if len(scan["packages"]) < 2:
        raise AssertionError(scan)
