#!/usr/bin/env python3
"""Probe 2: connect-timeout-only client MUST FAIL the read-timeout test.

Catalog tests_required[1]: negative control — a client configured with
connect-timeout only must FAIL this test, proving the test distinguishes
the two timeout kinds.

The slow-loris accepts immediately, so connect succeeds. Without a read
or throughput limit the client is still reading at T = read_timeout +
margin, so the TST-0132 assertion (network-fault within the deadline)
does not hold for that client.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from marketplace.download_client import (  # noqa: E402
    NETWORK_FAULT,
    connect_timeout_only_client,
    registry_download_client,
)
from loris_fixture import LorisServer  # noqa: E402
from scenario import (  # noqa: E402
    CONNECT_TIMEOUT_S,
    DEADLINE_S,
    MARGIN_S,
    READ_TIMEOUT_S,
    THROUGHPUT_FLOOR_BPS,
    THROUGHPUT_WINDOW_S,
)

OUT = HERE / "probe2-connect-only.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0132-probe2 {msg}")
    return 1


def main() -> int:
    connect_only = connect_timeout_only_client(connect_timeout_s=CONNECT_TIMEOUT_S)
    proper = registry_download_client(
        connect_timeout_s=CONNECT_TIMEOUT_S,
        read_timeout_s=READ_TIMEOUT_S,
        throughput_floor_bps=THROUGHPUT_FLOOR_BPS,
        throughput_window_s=THROUGHPUT_WINDOW_S,
        unit_timeout_s=None,
    )

    box: dict = {}

    def run_connect_only(url: str) -> None:
        box["result"] = connect_only.fetch_recorded(url)

    with LorisServer() as server:
        # Sanity: the proper client still trips on this same server.
        proper_slow = proper.fetch_recorded(server.slow_url)
        worker = threading.Thread(
            target=run_connect_only,
            args=(server.slow_url,),
            name="tst0132-connect-only",
            daemon=True,
        )
        worker.start()
        worker.join(timeout=DEADLINE_S)
        still_running = worker.is_alive()
        premature = box.get("result")
        server.close()
        worker.join(timeout=2.0)

    after_close = box.get("result")
    tst0132_assertion_holds_for_connect_only = False
    if not still_running and isinstance(premature, dict):
        elapsed = float(premature.get("elapsed_s") or 0.0)
        tst0132_assertion_holds_for_connect_only = (
            premature.get("ok") is False
            and premature.get("classification") == NETWORK_FAULT
            and elapsed <= DEADLINE_S
        )

    payload = {
        "proper_slow_ok": proper_slow.get("ok"),
        "proper_slow_classification": proper_slow.get("classification"),
        "proper_slow_kind": proper_slow.get("kind"),
        "proper_slow_elapsed_s": proper_slow.get("elapsed_s"),
        "connect_only_still_running_at_deadline": still_running,
        "connect_only_premature": None
        if premature is None
        else {k: v for k, v in premature.items() if k != "body"},
        "connect_only_after_close": None
        if after_close is None
        else {k: v for k, v in after_close.items() if k != "body"},
        "tst0132_assertion_holds_for_connect_only": tst0132_assertion_holds_for_connect_only,
        "read_timeout_s": READ_TIMEOUT_S,
        "margin_s": MARGIN_S,
        "deadline_s": DEADLINE_S,
    }
    OUT.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))

    if proper_slow.get("ok") is True:
        return fail("proper client did not trip on slow-loris (probe2 sanity)")
    if proper_slow.get("classification") != NETWORK_FAULT:
        return fail("proper client missing network-fault on slow-loris")
    if tst0132_assertion_holds_for_connect_only:
        return fail(
            "connect-timeout-only client satisfied the read-timeout test; "
            "the two timeout kinds are not distinguished"
        )
    if not still_running:
        # Finished before the deadline without matching the assertion —
        # still a discriminator, but we require the hang as the strong signal.
        return fail(
            "connect-timeout-only client returned before deadline "
            f"result={premature}"
        )

    print(
        "SUCCESS:TST-0132-probe2 connect-only still running at "
        f"deadline={DEADLINE_S:.3f}s; TST-0132 assertion FAILS for that client"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
