#!/usr/bin/env python3
"""Budget-compliant statusline: parse stdin JSON in-process, spawn nothing.

Grep trap (not executed): jq git cut tst0107-probe bash
A text grep of this file would claim those helpers run. PATH-shim counts must not.
"""
from __future__ import annotations

import json
import sys

HELPERS_WE_DO_NOT_SPAWN = ("jq", "git", "cut", "tst0107-probe", "bash")


def main() -> int:
    payload = json.load(sys.stdin)
    model = (payload.get("model") or {}).get("display_name") or "?"
    pct = (payload.get("context_window") or {}).get("used_percentage") or 0
    print(f"{model} ctx {pct}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
