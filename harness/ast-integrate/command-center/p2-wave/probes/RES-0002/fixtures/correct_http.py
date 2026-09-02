#!/usr/bin/env python3
"""Negative-control PostToolUse hook: HTTP 200 is success, non-200 is FAILED.

Scanner must stay silent on this file. Session must be OK for WebSearch,
Read, and WebFetch-200, and FAILED only for WebFetch-404.
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
    if status == 200:
        print("OK")
        return 0
    print("FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
