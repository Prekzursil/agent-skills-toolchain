#!/usr/bin/env python3
"""telemetry.py -- credential-forge capability (5b): statusline telemetry.

Fuses the lifecycle ledger (+ watchdog alerts, + optional hub/bridge usage
state when state/hub-usage.json exists) into a compact statusline segment
extending the estate's existing 5h/wk rate_limits pattern:

  forge:<n>keys exp:<min>d[ alerts:<k>]

Prints ONE line to stdout (names/counts/days only). Optionally persists the
segment to state/statusline-segment.txt for the statusline script to pick up.

Examples:
  python telemetry.py statusline
  python telemetry.py statusline --dry
  python telemetry.py statusline --format json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402

LEDGER = C.STATE_DIR / "ledger.json"
ALERTS = C.STATE_DIR / "alerts.json"
SEGMENT_FILE = C.STATE_DIR / "statusline-segment.txt"
HUB_USAGE = C.STATE_DIR / "hub-usage.json"  # optional fusion source (documented contract)


def collect() -> dict:
    ledger = C.load_json(LEDGER) or {}
    entries = ledger.get("entries", [])
    dated = [e for e in entries if isinstance(e.get("days_to_expiry"), (int, float))]
    expired = [e for e in dated if e["days_to_expiry"] <= 0]
    soon = [e for e in dated if 0 < e["days_to_expiry"] <= 7]
    alerts_doc = C.load_json(ALERTS) or {}
    alert_count = len(alerts_doc.get("alerts", []))
    usage = C.load_json(HUB_USAGE)
    return {
        "generated_at": ledger.get("generated_at"),
        "keys": len(entries),
        "keys_with_expiry": len(dated),
        "min_days": min((e["days_to_expiry"] for e in dated), default=None),
        "expired": len(expired),
        "expiring_soon": len(soon),
        "alerts": alert_count,
        "hub_usage_present": usage is not None,
        "hub_usage_keys": sorted(usage.keys()) if isinstance(usage, dict) else [],
    }


def render_segment(stats: dict) -> str:
    min_days = stats.get("min_days")
    if min_days is None:
        exp = "exp:?"
    elif min_days <= 0:
        exp = "exp:OVERDUE(%d)" % stats["expired"]
    else:
        exp = "exp:%dd" % int(min_days)
    segment = "forge:%dkeys %s" % (stats["keys"], exp)
    if stats["alerts"]:
        segment += " alerts:%d" % stats["alerts"]
    return segment


def cmd_statusline(args) -> int:
    stats = collect()
    segment = render_segment(stats)
    if args.format == "json":
        stats["segment"] = segment
        print(json.dumps(stats, indent=2, sort_keys=True))
        return 0
    print(segment)
    if stats["hub_usage_present"]:
        print("hub-usage fused (keys: %s)" % ",".join(stats["hub_usage_keys"][:4]), file=sys.stderr)
    if args.dry:
        print("DRY: segment file NOT written", file=sys.stderr)
        return 0
    SEGMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEGMENT_FILE.write_text(segment + "\n", encoding="utf-8")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="telemetry.py",
        description="statusline segment from ledger + alerts (+ optional hub usage)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("statusline", help="print the forge statusline segment")
    p.add_argument("--dry", action="store_true", help="print only; do not persist the segment file")
    p.add_argument("--format", choices=["segment", "json"], default="segment")
    args = ap.parse_args(argv)
    if args.cmd == "statusline":
        return cmd_statusline(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
