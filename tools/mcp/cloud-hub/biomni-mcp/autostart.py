#!/usr/bin/env python3
"""Auto-start the Biomni daemon set — one debug Chrome + broker + refresher per account.

Data-driven from ``~/.biomni-mcp/daemons.json`` (see ``daemons.example.json``): for
each account it (1) launches a debug Chrome (``--remote-debugging-port``) on the
account's persisted profile if that port isn't already up, (2) starts the
cookie-broker on the account's port, and (3) starts a ``refresher.py … watch`` that
keeps the account's cookie store fresh from that Chrome. Idempotent — it skips a
Chrome/broker that is already listening, so re-running (or a logon re-trigger) never
double-spawns.

The processes are spawned DETACHED (Windows: ``DETACHED_PROCESS``) so they outlive
this launcher. Register it to run at logon with the Startup-folder ``.bat`` (see the
docs) so the daemons come up on their own. Nothing here handles a secret: the
refresher reads the session cookie from your already-signed-in Chrome via CDP and
writes it (masked in its own logs) to the broker store.

Note: the debug Chrome profiles must already be SIGNED IN to Biomni (you do that
once, in a normal browser flow — Google allows it because it's a real, non-automated
sign-in). If a session has expired, that account's refresher reports it and you just
re-sign-in in its Chrome window.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(os.path.expanduser("~"), ".biomni-mcp", "daemons.json")
DEFAULT_CHROME = os.environ.get(
    "BIOMNI_CHROME", r"C:\Program Files\Google\Chrome\Application\chrome.exe"
)
WEB_URL = "https://biomni.phylo.bio"


def _port_up(port: int) -> bool:
    """True if a CDP/HTTP endpoint answers on 127.0.0.1:port."""
    try:
        urllib.request.urlopen(  # noqa: S310
            f"http://127.0.0.1:{port}/json/version", timeout=2
        )
        return True
    except urllib.error.HTTPError:
        return True  # something is listening (non-CDP) — good enough to skip
    except (urllib.error.URLError, OSError):
        return False


def _spawn(argv: list[str], env: dict | None = None) -> None:
    """Spawn a detached background process (its own session; outlives this launcher)."""
    kwargs: dict = {"env": {**os.environ, **(env or {})}}
    if os.name == "nt":
        # DETACHED_PROCESS (0x8) + no window: a true background daemon.
        kwargs["creationflags"] = 0x00000008 | 0x08000000
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(argv, **kwargs)  # noqa: S603


def _expand(path: str) -> str:
    return os.path.expanduser(os.path.expandvars(path))


def start_account(acct: dict, chrome: str) -> str:
    """Launch Chrome (if down) + broker + refresher for one account; return a status."""
    name = acct["name"]
    cdp = int(acct["cdp_port"])
    bport = int(acct["broker_port"])
    store = _expand(acct["token_file"])
    profile = _expand(acct["chrome_profile"])
    started = []
    if not _port_up(cdp):
        _spawn(
            [
                chrome,
                f"--remote-debugging-port={cdp}",
                "--window-position=-32000,-32000",  # off-screen: daemons must not pop windows (owner, 2026-09-29)
                "--window-size=1400,900",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
                WEB_URL,
            ]
        )
        started.append(f"chrome:{cdp}")
        time.sleep(4)  # give Chrome a moment before the refresher attaches
    if not _port_up(bport):
        _spawn(
            [sys.executable, os.path.join(HERE, "broker.py"), "--port", str(bport)],
            env={"BIOMNI_BROKER_TOKEN_FILE": store},
        )
        started.append(f"broker:{bport}")
    _spawn(
        [
            sys.executable,
            os.path.join(HERE, "refresher.py"),
            "--cdp",
            f"http://127.0.0.1:{cdp}",
            "--out-file",
            store,
            "watch",
        ]
    )
    started.append("refresher-watch")
    return f"[autostart] {name}: started {', '.join(started)} (store {store})"


def main(argv: list[str]) -> int:
    config = argv[0] if argv else os.environ.get("BIOMNI_DAEMONS", DEFAULT_CONFIG)
    if not os.path.exists(config):
        print(
            f"[autostart] no daemons config at {config} — copy daemons.example.json "
            "there and fill in your accounts (see the Biomni docs).",
            file=sys.stderr,
        )
        return 1
    cfg = json.load(open(config, encoding="utf-8"))
    chrome = cfg.get("chrome") or DEFAULT_CHROME
    for acct in cfg.get("accounts", []):
        print(start_account(acct, chrome))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
