#!/usr/bin/env python3
"""Positive-control inverted tool-sentinel: HTTP 200 compared equal to FAILED.

404 does not match 200, so a genuine fetch failure is labelled OK.
WebSearch and Read have no HTTP status and stay OK — WebFetch-specific.
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
    # INVERSION-COMPARE: maps HTTP 200 to FAILED
    if status == 200:
        print("FAILED")
        return 200
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
