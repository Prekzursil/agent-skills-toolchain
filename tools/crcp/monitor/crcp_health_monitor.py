#!/usr/bin/env python3
"""Persistent CRCP health poller for `mon crcp`.

Refreshes reports/wfmon_crcp_health.json and prints a compact board.
Does not spawn MCP servers. Ctrl+C to exit.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Resolve package: prefer sibling tools/crcp on PYTHONPATH
HERE = Path(__file__).resolve().parent
CRP_ROOT = HERE.parent  # tools/crcp
if str(CRP_ROOT) not in sys.path:
    sys.path.insert(0, str(CRP_ROOT))

from crcp.health import full_health, health_table, write_wfmon_snippet  # noqa: E402


def main() -> int:
    interval = float(os.environ.get("CRCP_HEALTH_INTERVAL_SEC", "30"))
    snippet = CRP_ROOT / "reports" / "wfmon_crcp_health.json"
    print(f"CRCP health monitor interval={interval}s snippet={snippet}")
    print("Ctrl+C to stop.\n")
    while True:
        try:
            report = full_health()
            write_wfmon_snippet(report, snippet)
            # clear-ish board
            print("\n" + "=" * 72)
            print(health_table(report))
            print(f"snippet → {snippet}")
        except Exception as e:
            print(f"FAILED:health {type(e).__name__}: {e}", file=sys.stderr)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped")
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
