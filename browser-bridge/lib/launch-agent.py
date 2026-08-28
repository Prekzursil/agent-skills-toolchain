#!/usr/bin/env python3
"""Launch a dedicated Chrome/Edge persistent profile via Playwright (pipe CDP)
and load the audited unpacked extension with Extensions.loadUnpacked.

Never pointed at the human/default User Data directory. Token is read from
CHROME_BRIDGE_TOKEN (never argv, never written to the ready JSON).
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

AGENT_ID = "bdccimcedobipcmhcikcnakjdemiechj"


def _profiles_root() -> Path:
    return (Path.home() / ".agents" / "browser-profiles").resolve()


def _forbidden_human_dirs() -> list[Path]:
    local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return [
        local / "Google" / "Chrome" / "User Data",
        local / "Google" / "Chrome Beta" / "User Data",
        local / "Google" / "Chrome SxS" / "User Data",
        local / "Microsoft" / "Edge" / "User Data",
        local / "Microsoft" / "Edge Beta" / "User Data",
        local / "Microsoft" / "Edge Dev" / "User Data",
    ]


def assert_agent_profile(user_data: Path) -> None:
    resolved = user_data.resolve()
    root = _profiles_root()
    try:
        resolved.relative_to(root)
    except ValueError:
        print(f"FAILED:launch-agent user-data-dir is not under {root}", file=sys.stderr)
        raise SystemExit(2)
    resolved_s = str(resolved).lower()
    for forbidden in _forbidden_human_dirs():
        try:
            f = forbidden.resolve()
        except OSError:
            f = forbidden
        if resolved_s.startswith(str(f).lower()):
            print("FAILED:launch-agent refusing human/default Chrome or Edge User Data", file=sys.stderr)
            raise SystemExit(2)


def inject_extension_token(context, session, extension_id: str, port: int, token: str) -> str:
    """Write the hub token into chrome.storage.local. Never logs the token."""
    payload = {"token": token, "port": port, "enabled": True}

    deadline = time.time() + 12
    while time.time() < deadline:
        for worker in list(context.service_workers):
            url = getattr(worker, "url", "") or ""
            if extension_id in url or url.startswith("chrome-extension://"):
                try:
                    worker.evaluate(
                        """async (cfg) => {
                            await chrome.storage.local.set(cfg);
                            try { chrome.runtime.sendMessage({ type: "reconnect" }); } catch (e) {}
                            return true;
                        }""",
                        payload,
                    )
                    return "playwright-worker"
                except Exception:
                    pass
        time.sleep(0.3)

    try:
        targets = session.send("Target.getTargets")
    except Exception as exc:
        print(f"FAILED:launch-agent token inject: no service worker ({exc})", file=sys.stderr)
        raise SystemExit(1)
    infos = targets.get("targetInfos") if isinstance(targets, dict) else []
    sw = None
    for info in infos or []:
        url = str(info.get("url") or "")
        typ = str(info.get("type") or "")
        if extension_id in url and typ in ("service_worker", "background_page"):
            sw = info
            break
    if not sw:
        print("FAILED:launch-agent token inject: extension service worker not found", file=sys.stderr)
        raise SystemExit(1)
    attached = session.send("Target.attachToTarget", {"targetId": sw["targetId"], "flatten": False})
    session_id = attached.get("sessionId") if isinstance(attached, dict) else None
    if not session_id:
        print("FAILED:launch-agent token inject: attachToTarget produced no session", file=sys.stderr)
        raise SystemExit(1)
    expression = (
        "(async (cfg) => { await chrome.storage.local.set(cfg); "
        "try { chrome.runtime.sendMessage({ type: 'reconnect' }); } catch (e) {} "
        "return true; })(" + json.dumps(payload) + ")"
    )
    message = {
        "id": 1,
        "method": "Runtime.evaluate",
        "params": {"expression": expression, "awaitPromise": True, "returnByValue": True},
    }
    session.send("Target.sendMessageToTarget", {"sessionId": session_id, "message": json.dumps(message)})
    time.sleep(0.6)
    return "cdp-sendMessageToTarget"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", required=True, choices=("chrome", "edge"))
    parser.add_argument("--user-data-dir", required=True)
    parser.add_argument("--extension-dir", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--hub-port", type=int, default=8770)
    parser.add_argument("--expected-extension-id", default=AGENT_ID)
    args = parser.parse_args()

    token = os.environ.get("CHROME_BRIDGE_TOKEN", "").strip()
    if len(token) < 16:
        print("FAILED:launch-agent CHROME_BRIDGE_TOKEN missing or too short", file=sys.stderr)
        return 2

    user_data = Path(args.user_data_dir)
    assert_agent_profile(user_data)
    user_data.mkdir(parents=True, exist_ok=True)
    extension_dir = str(Path(args.extension_dir).resolve())
    expected_name = Path(extension_dir).name.lower()
    if expected_name not in ("extension-agent",):
        print(
            f"FAILED:launch-agent refusing to load extension folder {expected_name} "
            "(agent lane loads extension-agent only; LIVE is owner-unpacked extension-live)",
            file=sys.stderr,
        )
        return 2
    if "extension-live" in extension_dir.lower():
        print("FAILED:launch-agent refusing to auto-load extension-live into an agent profile", file=sys.stderr)
        return 2

    ready = Path(args.ready_file)
    stop = Path(args.stop_file)
    if stop.exists():
        stop.unlink()

    channel = "chrome" if args.browser == "chrome" else "msedge"

    def request_stop(*_args) -> None:
        stop.write_text("stop", encoding="utf-8")

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
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
            loaded_id = ""
            if isinstance(loaded, dict):
                loaded_id = str(loaded.get("id") or loaded.get("extensionId") or "")
            if args.expected_extension_id and loaded_id and loaded_id != args.expected_extension_id:
                print(
                    f"FAILED:launch-agent extension id mismatch got={loaded_id} expected={args.expected_extension_id}",
                    file=sys.stderr,
                )
                context.close()
                return 1
            if args.expected_extension_id and not loaded_id:
                loaded_id = args.expected_extension_id
            time.sleep(1.0)
            listed = session.send("Extensions.getExtensions")
            inject_how = inject_extension_token(context, session, loaded_id or args.expected_extension_id, args.hub_port, token)
            payload = {
                "ok": True,
                "browser": args.browser,
                "channel": channel,
                "user_data_dir": str(user_data),
                "extension_dir": extension_dir,
                "loaded": loaded,
                "extensions": listed,
                "expected_extension_id": args.expected_extension_id,
                "token_injected": inject_how,
                "hub_port": args.hub_port,
                "pid": os.getpid(),
            }
            ready.parent.mkdir(parents=True, exist_ok=True)
            ready.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(
                f"SUCCESS:launch-agent loaded_id={loaded_id} token_injected={inject_how} listed_ok=true",
                flush=True,
            )
            while not stop.exists():
                time.sleep(0.4)
            context.close()
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f"FAILED:launch-agent {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
