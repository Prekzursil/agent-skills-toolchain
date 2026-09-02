#!/usr/bin/env python3
"""Planted credential-file consumer. Unset vs wrong must differ."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

EXPECTED = "aud0079-ok-token-not-a-secret"


def main() -> int:
    raw = os.environ.get("AUD0079_CREDENTIAL_FILE")
    if not raw:
        print("MISSING-FILE-ENV:AUD0079_CREDENTIAL_FILE")
        return 2
    path = Path(raw)
    if not path.is_file():
        print("MISSING-FILE")
        return 2
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("REJECTED-FILE:unreadable")
        return 3
    token = doc.get("token") if isinstance(doc, dict) else None
    if token != EXPECTED:
        print("REJECTED-FILE:token")
        return 3
    print("OK-FILE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
