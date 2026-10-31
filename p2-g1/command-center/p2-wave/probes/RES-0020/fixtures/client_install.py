#!/usr/bin/env python3
"""Throwaway loopback plugin-install fixture for RES-0020 (recreated 2026-10-25,
wave-2 shard 17, faithful to the recorded role: the fixture client fetches the
plugin tarball, honours the telemetry kill-switches, and POSTs telemetry only
when enabled). Prints one JSON line. The collector stores key NAMES only."""
from __future__ import annotations
import argparse, json, os, sys, urllib.request

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--marketplace", required=True)
    ap.add_argument("--telemetry", required=True)
    ap.add_argument("--vendor", required=True)
    ap.add_argument("--settings")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    offline = os.environ.get("OFFLINE") == "1"
    out = {"marketplace": False, "telemetry": False, "telemetry_keys": [],
           "vendor": False, "offline": offline}
    if not offline:
        try:
            u = a.marketplace + ("?refresh=1" if a.refresh else "")
            urllib.request.urlopen(u, timeout=5).read(16)
            out["marketplace"] = True
        except Exception:
            out["marketplace"] = False
        env_off = os.environ.get("TELEMETRY_DISABLED") in ("1", "true")
        set_off = False
        if a.settings and os.path.isfile(a.settings):
            try:
                with open(a.settings, encoding="utf-8") as fh:
                    cfg = json.load(fh)
                set_off = cfg.get("telemetry", {}).get("enabled") is False
            except Exception:
                set_off = False
        if not (env_off or set_off):
            body = json.dumps({"event": "install", "plugin_id": "fixture-plugin",
                               "os": sys.platform, "hostname": "loopback-host",
                               "session_id": "fixture-session",
                               "api_key": "REDACTED-BY-FIXTURE"}).encode()
            req = urllib.request.Request(a.telemetry, data=body,
                                         headers={"Content-Type": "application/json"})
            try:
                urllib.request.urlopen(req, timeout=5).read(16)
                out["telemetry"] = True
                out["telemetry_keys"] = ["event", "plugin_id", "os", "hostname",
                                         "session_id", "api_key"]
            except Exception:
                out["telemetry"] = False
    if os.environ.get("MCP_VENDOR_EGRESS") == "1":
        try:
            urllib.request.urlopen(a.vendor, timeout=5).read(16)
            out["vendor"] = True
        except Exception:
            out["vendor"] = False
    print(json.dumps(out))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
