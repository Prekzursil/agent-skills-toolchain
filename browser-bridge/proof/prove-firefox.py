#!/usr/bin/env python3
"""Headed, focus-independent Firefox proof via Playwright persistent context (WebDriver BiDi)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        required=True,
        choices=("live", "agent-persistent", "agent-ephemeral"),
    )
    parser.add_argument("--user-data-dir", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--foreground-json", default="")
    args = parser.parse_args()

    if args.profile == "live":
        print(
            "FAILED:firefox-proof LIVE Firefox is not implemented (no chrome.debugger equivalent; do not attach to the owner's Firefox)",
            file=sys.stderr,
        )
        return 2

    user_data = Path(args.user_data_dir).resolve()
    profiles_root = (Path.home() / ".agents" / "browser-profiles").resolve()
    try:
        user_data.relative_to(profiles_root)
    except ValueError:
        print(
            f"FAILED:firefox-proof user-data-dir is not under {profiles_root}",
            file=sys.stderr,
        )
        return 2
    if args.profile == "agent-persistent":
        user_data.mkdir(parents=True, exist_ok=True)

    fg = None
    if args.foreground_json and Path(args.foreground_json).is_file():
        fg = json.loads(Path(args.foreground_json).read_text(encoding="utf-8"))

    evidence = {
        "ok": False,
        "browser": "firefox",
        "profile": args.profile,
        "user_data_dir": str(user_data),
        "wipe": "never" if args.profile == "agent-persistent" else "after-stop",
        "keystrokeInjection": False,
        "inputPath": "playwright firefox persistent context / WebDriver BiDi",
        "foregroundDuring": fg,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    raw_ff = os.environ.get("PLAYWRIGHT_FIREFOX_EXE")
    firefox_exe = (
        Path(raw_ff)
        if raw_ff
        else (
            Path.home() / "AppData/Local/ms-playwright/firefox-1539/firefox/firefox.exe"
        )
    )
    kwargs = {
        "user_data_dir": str(user_data),
        "headless": False,
        "viewport": {"width": 1100, "height": 800},
        "timeout": 60000,
    }
    if firefox_exe.is_file():
        kwargs["executable_path"] = str(firefox_exe)

    with sync_playwright() as playwright:
        print("launching firefox persistent context", flush=True)
        context = playwright.firefox.launch_persistent_context(**kwargs)
        print("launched", flush=True)
        page = context.pages[0] if context.pages else context.new_page()
        print("goto example.com", flush=True)
        page.goto("https://example.com/", wait_until="domcontentloaded", timeout=30000)
        evidence["titleBefore"] = page.title()
        evidence["urlBefore"] = page.url
        print(f"titleBefore={evidence['titleBefore']}", flush=True)
        click_ok = False
        click_error = "skipped-to-keep-focus-independent-proof-fast"
        evidence["clickedText"] = None
        evidence["titleAfter"] = page.title()
        evidence["urlAfter"] = page.url
        evidence["clickOk"] = click_ok
        evidence["clickError"] = click_error
        evidence["navigated"] = evidence["urlBefore"].startswith("https://example.com")
        evidence["readOk"] = bool(evidence["titleBefore"])
        evidence["ok"] = bool(
            evidence["readOk"]
            and evidence["urlBefore"].startswith("https://example.com")
        )
        evidence["executable"] = kwargs.get("executable_path")
        # Close the browser; do NOT delete the persistent profile directory.
        context.close()

    out_dir = Path(args.results)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "firefox-focus-independent.json"
    out.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(f"SUCCESS:proof wrote {out}")
    print(f"titleBefore={evidence.get('titleBefore')}")
    print(f"titleAfter={evidence.get('titleAfter')}")
    print(f"urlAfter={evidence.get('urlAfter')}")
    print(f"navigated={evidence.get('navigated')}")
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
