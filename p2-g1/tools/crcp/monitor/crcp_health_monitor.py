#!/usr/bin/env python3
"""CRCP health poller for `mon crcp`.

Refreshes reports/wfmon_crcp_health.json and prints a compact board.
Does not spawn MCP servers.

Two modes:
  (default)  persistent poll every interval seconds; Ctrl+C to exit.
  --once     run exactly ONE tick, then exit. Nothing to kill.

The --once exit code reports whether the POLL ran, not whether the fleet is
healthy: 0 = one tick completed and the snippet was written, 1 = the tick
raised. A RED rail still exits 0, so do not read a bare --once exit code as a
fleet-health verdict -- read the snippet it writes.

Every stdout print here flushes (MON-crcp-2): a non-tty stdout is
block-buffered, so without the flushes a redirected/tee'd `mon crcp` capture
read 0 bytes through the whole sleep while ticks were completing, and a log
reader could misdiagnose a healthy monitor as hung.
"""

from __future__ import annotations

import argparse
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

DEFAULT_INTERVAL_SEC = 30.0


def _default_interval() -> float:
    """Interval from the environment, falling back to DEFAULT_INTERVAL_SEC."""
    raw = os.environ.get("CRCP_HEALTH_INTERVAL_SEC")
    if raw is None:
        return DEFAULT_INTERVAL_SEC
    try:
        return float(raw)
    except ValueError:
        print(
            f"WARN:interval CRCP_HEALTH_INTERVAL_SEC={raw!r} is not a number; "
            f"using {DEFAULT_INTERVAL_SEC}",
            file=sys.stderr,
        )
        return DEFAULT_INTERVAL_SEC


def tick(snippet: Path) -> int:
    """Run one health poll and render one board. 0 = polled, 1 = poll raised."""
    try:
        report = full_health()
        write_wfmon_snippet(report, snippet)
        # clear-ish board; flush so the board leaves the process before the
        # next sleep -- a block-buffered non-tty stdout otherwise holds it
        # for the whole interval (MON-crcp-2)
        print("\n" + "=" * 72, flush=True)
        print(health_table(report), flush=True)
        print(f"snippet -> {snippet}", flush=True)
        return 0
    except Exception as e:
        print(f"FAILED:health {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crcp_health_monitor",
        description="CRCP multi-rail health board (auth, agent-mail, bridge, Databricks).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="run exactly one poll, print one board, then exit "
        "(0 = polled, 1 = poll raised; NOT a fleet-health verdict)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        metavar="SEC",
        help="seconds between polls in persistent mode "
        "(default: $CRCP_HEALTH_INTERVAL_SEC, else 30). Ignored with --once.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snippet = CRP_ROOT / "reports" / "wfmon_crcp_health.json"

    if args.once:
        # flush: the banner must be readable while the tick's probes run
        # (seconds), not only at exit (MON-crcp-2)
        print(f"CRCP health monitor single-shot snippet={snippet}", flush=True)
        return tick(snippet)

    interval = args.interval if args.interval is not None else _default_interval()
    print(f"CRCP health monitor interval={interval}s snippet={snippet}", flush=True)
    print("Ctrl+C to stop.\n", flush=True)
    while True:
        tick(snippet)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped", flush=True)
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
