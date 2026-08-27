#!/usr/bin/env python3
"""Launch a dedicated Chrome/Edge persistent profile via Playwright (pipe CDP)
and load the audited unpacked extension with Extensions.loadUnpacked.

Branded Chrome 137+ ignores --load-extension and the HTTP debugging-port
Extensions domain is a no-op (getExtensions stays empty). Playwright's pipe
session is the sanctioned path.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


ANTI_THROTTLE = [
    "--enable-unsafe-extension-debugging",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--no-first-run",
    "--no-default-browser-check",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", required=True, choices=("chrome", "edge"))
    parser.add_argument("--user-data-dir", required=True)
    parser.add_argument("--extension-dir", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--stop-file", required=True)
    args = parser.parse_args()

    user_data = Path(args.user_data_dir)
    user_data.mkdir(parents=True, exist_ok=True)
    extension_dir = str(Path(args.extension_dir).resolve())
    ready = Path(args.ready_file)
    stop = Path(args.stop_file)
    if stop.exists():
        stop.unlink()

    channel = "chrome" if args.browser == "chrome" else "msedge"

    def request_stop(*_args) -> None:
        stop.write_text("stop", encoding="utf-8")

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            channel=channel,
            headless=False,
            args=ANTI_THROTTLE,
            ignore_default_args=["--disable-extensions"],
            viewport={"width": 1100, "height": 800},
        )
        browser = context.browser
        if browser is None:
            print("FAILED:launch-agent persistent context has no browser object", file=sys.stderr)
            context.close()
            return 1
        session = browser.new_browser_cdp_session()
        loaded = session.send("Extensions.loadUnpacked", {"path": extension_dir})
        time.sleep(1.0)
        listed = session.send("Extensions.getExtensions")
        payload = {
            "ok": True,
            "browser": args.browser,
            "channel": channel,
            "user_data_dir": str(user_data),
            "extension_dir": extension_dir,
            "loaded": loaded,
            "extensions": listed,
            "pid": os.getpid(),
        }
        ready.parent.mkdir(parents=True, exist_ok=True)
        ready.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"SUCCESS:launch-agent loaded={loaded} listed={listed}", flush=True)
        while not stop.exists():
            time.sleep(0.4)
        context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
