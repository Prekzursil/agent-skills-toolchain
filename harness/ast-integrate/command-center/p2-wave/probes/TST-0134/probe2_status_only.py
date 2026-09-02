#!/usr/bin/env python3
"""Probe 2: negative control — a status-only client must fail this test.

The content-aware client still rejects the HTML 200 interstitial. A client
that keys only on HTTP status accepts the same fixture and writes HTML into
the index, proving the test distinguishes the two.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

from marketplace.http_registry import (  # noqa: E402
    RegistryFetchClient,
    StatusOnlyRegistryClient,
    UnexpectedContentTypeError,
)
from harness import FixtureServer, seed_index, stat_index  # noqa: E402

ART = REPO / "command-center/receipts/TST-0134.json"
SENTINEL = "SUCCESS:TST-0134"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0134-probe2 {msg}")
    return 1


def main() -> int:
    aware = RegistryFetchClient()
    status_only = StatusOnlyRegistryClient()
    srv = FixtureServer()
    try:
        with tempfile.TemporaryDirectory(prefix="tst0134-p2-") as tmp:
            bad_path = Path(tmp) / "status-only-index"
            before_bad = seed_index(bad_path)
            accepted = False
            try:
                result = status_only.fetch_index(srv.interstitial_url, bad_path)
                accepted = bool(result.get("ok"))
            except Exception as exc:  # noqa: BLE001
                return fail(
                    f"status-only client rejected interstitial (cannot distinguish): {exc}"
                )
            if not accepted:
                return fail("status-only client did not accept HTTP 200")
            after = stat_index(bad_path)
            body = bad_path.read_bytes()
            if b"<html" not in body.lower() and b"captive" not in body.lower():
                return fail("status-only client did not persist HTML interstitial")
            if after["sha256"] == before_bad["sha256"]:
                return fail("status-only index still seeded")

            aware_path = Path(tmp) / "aware-index"
            seed_index(aware_path)
            before = stat_index(aware_path)
            aware_rejected = False
            try:
                aware.fetch_index(srv.interstitial_url, aware_path)
            except UnexpectedContentTypeError:
                aware_rejected = True
            except Exception as exc:  # noqa: BLE001
                return fail(f"aware client wrong exception {type(exc).__name__}: {exc}")
            if not aware_rejected:
                return fail("content-aware client accepted interstitial")
            if stat_index(aware_path)["mtime_ns"] != before["mtime_ns"]:
                return fail("aware client mutated index")

            tst0134_assertion_on_status_only = not accepted
            if tst0134_assertion_on_status_only:
                return fail("status-only unexpectedly satisfied the content-type assertion")
    finally:
        srv.close()

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel absent")
    nc = (doc.get("report") or {}).get("negative_control") or {}
    if nc.get("status_only_accepted_interstitial") is not True:
        return fail("receipt negative_control.status_only_accepted_interstitial != true")

    out = {
        "aware_rejected": True,
        "pass": True,
        "probe": "probe2-status-only-negative-control",
        "status_only_accepted_interstitial": True,
        "status_only_fails_this_test": True,
        "unit_id": "TST-0134",
        "wrote_html": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("status-only accepted HTML 200 (fails TST-0134); aware rejected")
    print("SUCCESS:TST-0134-probe2 status-only negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
