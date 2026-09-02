#!/usr/bin/env python3
"""Probe 1: detector control — reachable URL succeeds; broken URL does not.

Catalog test: fetch a known-reachable control URL through the same path and
require success, so a blocked verdict cannot be a broken fetcher.
Also re-fetches the BBC geolocation 403 so a geo-block is not a dead fetcher.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fetchutil as F  # noqa: E402
import targets as T  # noqa: E402

ART = REPO / (
    "command-center/research/sources-frontier/"
    "RES-0179-jurisdiction-source-accessibility-scoping.json"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0179-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 1024:
        return fail("artifact missing or too small")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "RES-0179":
        return fail(f"unit_id={doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:RES-0179" not in text:
        return fail("sentinel-absent")

    control = F.fetch(T.CONTROL_URL, timeout=15.0, max_bytes=8192)
    negative = F.fetch(T.NEGATIVE_CONTROL_URL, timeout=15.0, max_bytes=4096)
    geo = F.fetch(T.GEO_BLOCK_URL, timeout=15.0, max_bytes=4096)

    print(
        json.dumps(
            {
                "control_status": control.get("http_status"),
                "control_ok": control.get("ok_2xx"),
                "negative_status": negative.get("http_status"),
                "negative_ok": negative.get("ok_2xx"),
                "geo_status": geo.get("http_status"),
                "geo_head": str(geo.get("body_head") or "")[:180],
            },
            sort_keys=True,
        )
    )

    if not control.get("ok_2xx"):
        return fail("control URL did not succeed — blocked verdicts would be untrustworthy")
    if negative.get("ok_2xx"):
        return fail("negative control unexpectedly succeeded — detector silent in both states")
    if negative.get("http_status") != 404:
        return fail(f"negative control expected 404 got {negative.get('http_status')}")
    if geo.get("http_status") != 403:
        return fail(f"geo example expected 403 got {geo.get('http_status')}")
    if "geolocation" not in str(geo.get("body_head") or ""):
        return fail("geo example 403 body missing result=geolocation")

    dc = doc.get("detector_control") or {}
    if not dc.get("control_ok"):
        return fail("artifact detector_control.control_ok is not true")
    if not dc.get("negative_not_ok"):
        return fail("artifact detector_control.negative_not_ok is not true")
    if not dc.get("blocked_is_not_control_failure"):
        return fail("artifact did not pair blocked example with live control")

    print(
        "control=200 negative=404 geo=403-geolocation "
        "fetcher-up=True blocked-not-dead-fetcher=True"
    )
    print("SUCCESS:RES-0179-probe1 detector-control both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
