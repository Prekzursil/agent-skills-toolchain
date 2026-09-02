#!/usr/bin/env python3
"""Positive-control inverted tool-sentinel: HTTP status used as process exit.

A successful WebFetch (HTTP 200) therefore exits 200 and prints FAILED.
WebSearch and Read carry no HTTP status, so they print OK and exit 0.
A 404 fetch also exits non-zero (404) and prints FAILED: FAILED in both
HTTP states, so as a fetch-quality detector this measures nothing.
"""
from __future__ import annotations

import json
import sys


def extract_status(event: dict):
    resp = event.get("tool_response") or {}
    if not isinstance(resp, dict):
        return None
    for key in ("status_code", "http_status", "httpStatus", "status"):
        val = resp.get(key)
        if isinstance(val, bool):
            continue
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    return None


def main() -> int:
    event = json.load(sys.stdin)
    status = extract_status(event)
    if status is None:
        print("OK")
        return 0
    # INVERSION-COMPARE: treat HTTP status as process exit (200 -> FAILED)
    if status != 0:
        print("FAILED")
        return status
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
