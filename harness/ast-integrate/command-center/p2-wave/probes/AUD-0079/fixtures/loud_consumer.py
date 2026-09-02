#!/usr/bin/env python3
"""Planted loud-fail credential consumer (both-states control)."""
from __future__ import annotations

import os
import sys

EXPECTED = "aud0079-ok-token-not-a-secret"


def main() -> int:
    if not os.environ.get("AUD0079_PROBE_TOKEN"):
        print("MISSING:AUD0079_PROBE_TOKEN")
        return 2
    got = os.environ.get("AUD0079_PROBE_TOKEN") or ""
    if got != EXPECTED:
        print("REJECTED:AUD0079_PROBE_TOKEN")
        return 3
    print("OK:AUD0079_PROBE_TOKEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
