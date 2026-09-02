#!/usr/bin/env python3
"""Probe 1: slow-loris trips READ/throughput timeout; fast twin completes.

Catalog tests_required[0]: both-states control — a normal-speed response
on the same endpoint completes.

Evidence: wall-clock vs declared read timeout, and classification
`network-fault` (not generic `unit-timeout`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from marketplace.download_client import (  # noqa: E402
    NETWORK_FAULT,
    UNIT_TIMEOUT,
    registry_download_client,
)
from loris_fixture import LorisServer  # noqa: E402
from scenario import (  # noqa: E402
    CONNECT_TIMEOUT_S,
    DEADLINE_S,
    FAST_BODY,
    MARGIN_S,
    READ_TIMEOUT_S,
    THROUGHPUT_FLOOR_BPS,
    THROUGHPUT_WINDOW_S,
    UNIT_TIMEOUT_S,
)

OUT = HERE / "probe1-both-states.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0132-probe1 {msg}")
    return 1


def main() -> int:
    client = registry_download_client(
        connect_timeout_s=CONNECT_TIMEOUT_S,
        read_timeout_s=READ_TIMEOUT_S,
        throughput_floor_bps=THROUGHPUT_FLOOR_BPS,
        throughput_window_s=THROUGHPUT_WINDOW_S,
        unit_timeout_s=UNIT_TIMEOUT_S,
    )
    with LorisServer() as server:
        slow = client.fetch_recorded(server.slow_url)
        fast = client.fetch_recorded(server.fast_url)
        accepted = server.accepted

    payload = {
        "slow": {k: v for k, v in slow.items() if k != "body"},
        "slow_body_len": len(slow.get("body") or b""),
        "fast": {k: v for k, v in fast.items() if k != "body"},
        "fast_body_len": len(fast.get("body") or b""),
        "fast_body_ok": (fast.get("body") or b"") == FAST_BODY,
        "accepted": accepted,
        "read_timeout_s": READ_TIMEOUT_S,
        "margin_s": MARGIN_S,
        "deadline_s": DEADLINE_S,
        "unit_timeout_s": UNIT_TIMEOUT_S,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))

    if slow.get("ok") is True:
        return fail("slow-loris completed instead of timing out")
    if slow.get("classification") != NETWORK_FAULT:
        return fail(
            f"slow classification={slow.get('classification')!r} want={NETWORK_FAULT}"
        )
    if slow.get("kind") == UNIT_TIMEOUT or slow.get("classification") == UNIT_TIMEOUT:
        return fail("slow-loris classified as generic unit-timeout")
    elapsed = float(slow.get("elapsed_s") or 0.0)
    if elapsed > DEADLINE_S:
        return fail(
            f"elapsed={elapsed:.3f}s exceeds read_timeout {READ_TIMEOUT_S}s "
            f"+ margin {MARGIN_S}s (deadline {DEADLINE_S}s)"
        )
    if elapsed > UNIT_TIMEOUT_S * 0.9:
        return fail(f"elapsed={elapsed:.3f}s looks like the generic unit timeout")
    if elapsed < THROUGHPUT_WINDOW_S * 0.5:
        return fail(f"elapsed={elapsed:.3f}s too fast to be a read/throughput wait")

    if fast.get("ok") is not True:
        return fail(f"fast twin failed: {fast}")
    if (fast.get("body") or b"") != FAST_BODY:
        return fail("fast twin body mismatch")
    fast_elapsed = float(fast.get("elapsed_s") or 0.0)
    if fast_elapsed >= READ_TIMEOUT_S:
        return fail(f"fast twin elapsed={fast_elapsed:.3f}s >= read timeout")
    if accepted < 2:
        return fail(f"server accepted {accepted} connections, want >= 2")

    print(
        "SUCCESS:TST-0132-probe1 slow classification={0} kind={1} "
        "elapsed={2:.3f}s deadline={3:.3f}s fast_ok=True".format(
            slow.get("classification"),
            slow.get("kind"),
            elapsed,
            DEADLINE_S,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
