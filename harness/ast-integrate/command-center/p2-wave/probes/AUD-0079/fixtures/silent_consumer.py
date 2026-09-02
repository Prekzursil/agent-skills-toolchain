#!/usr/bin/env python3
"""Planted silent-degrade consumer. Unset and wrong both exit 0."""
from __future__ import annotations

import os
import sys


def main() -> int:
    token = os.environ.get("AUD0079_PROBE_TOKEN", "anonymous")
    print("PROCEED:AUD0079_PROBE_TOKEN:present=%s:len=%d" % ("AUD0079_PROBE_TOKEN" in os.environ, len(token)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
