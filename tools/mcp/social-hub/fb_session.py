#!/usr/bin/env python3
"""fb_session -- re-runnable Facebook cookie refresh for the fb-messenger backend.

The Instagram rail stays alive because a session file is refreshed on demand; the
Facebook rail rotted for six weeks because nothing refreshed ``cookies.json``.
This tool closes that gap and makes the FB auth SELF-HEALING, mirroring IG's
login-once model:

1. Drive the Playwright cookie exporter (``fb-reels-uploader/fb-session-export.mjs``)
   which opens a browser, lets the owner log into Facebook ONCE (no password is
   ever typed by any script here), and writes ``cookies.json`` in the exact shape
   ``fbchat_muqit`` loads. It reuses the shared fb-reels persistent profile, so a
   single Facebook login serves Reel posting, cookie refresh, and Messenger.
2. VERIFY the written file actually authenticates by calling the backend's
   ``whoami`` tool over MCP -- never by inspecting the file. A cookies.json that
   parses but no longer authenticates is a failure, and this reports it as one.

Run it again whenever ``whoami`` starts failing; that is the whole point.

Security: this module reports cookie NAMES, counts, and the ``whoami`` verdict
only. It NEVER prints, logs, or returns a cookie value, token, uid, or name text.
``cookies.json`` is radioactive -- it is gitignored and must never be committed.

Usage::

    python fb_session.py [--out PATH] [--profile DIR] [--headless] [--timeout SEC]
    python fb_session.py --verify-only [--out PATH]   # just re-check whoami
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "_shared"))

from backends import default_backends  # noqa: E402

EXPORTER = os.path.normpath(
    os.path.join(_HERE, "..", "fb-reels-uploader", "fb-session-export.mjs")
)
VERIFY_TIMEOUT = 60.0  # seconds to wait for the backend's whoami round-trip


def _fb_spec():
    """The fb-messenger BackendSpec (its launch argv + default cookies path)."""
    for spec in default_backends():
        if spec.id == "fb":
            return spec
    raise RuntimeError("fb backend spec not found")  # pragma: no cover


def default_cookies_path() -> str:
    """Canonical cookies.json path: FB_COOKIES_PATH, else the fb slot's dest."""
    env = os.environ.get("FB_COOKIES_PATH")
    if env:
        return env
    spec = _fb_spec()
    for slot in spec.account.files if spec.account else ():
        if slot.key == "cookies":
            return slot.dest
    raise RuntimeError("no cookies FileSlot on the fb backend")  # pragma: no cover


def run_export(
    out: str,
    profile: str | None = None,
    headless: bool = False,
    timeout: int = 600,
) -> tuple[bool, str]:
    """Run the Node/Playwright exporter; return (ok, terminal_marker_line).

    The owner logs into Facebook in the window that opens (this never types a
    credential). Progress goes to stderr; the last stdout line is the marker.
    """
    argv = ["node", EXPORTER, "--out", out, "--timeout", str(timeout)]
    if profile:
        argv += ["--profile", profile]
    if headless:
        argv.append("--headless")
    try:
        proc = subprocess.run(
            argv,
            cwd=os.path.dirname(EXPORTER),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout + 120,
        )
    except FileNotFoundError:
        return False, "FAILED:fb-session node not on PATH"
    except subprocess.TimeoutExpired:
        return False, "FAILED:fb-session exporter timed out"
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    marker = ""
    for line in (proc.stdout or "").splitlines():
        if line.startswith(("SUCCESS:", "FAILED:")):
            marker = line.strip()
    ok = proc.returncode == 0 and marker.startswith("SUCCESS:")
    return ok, marker or f"FAILED:fb-session exporter exited {proc.returncode}"


def _mcp_whoami(cmd: tuple[str, ...], env: dict[str, str]) -> dict:
    """Spawn the fb backend, call the whoami tool, return a structured verdict.

    Reuses only the stdlib. Returns ``{authenticated, name_present, detail}`` and
    never surfaces a value.
    """
    proc = subprocess.Popen(
        list(cmd),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    q: "queue.Queue[str | None]" = queue.Queue()

    def _reader() -> None:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                q.put(line)
        finally:
            q.put(None)

    threading.Thread(target=_reader, daemon=True).start()

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")  # type: ignore[union-attr]
        proc.stdin.flush()  # type: ignore[union-attr]

    def wait_for(want_id, deadline: float) -> dict:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("whoami timed out")
            try:
                line = q.get(timeout=remaining)
            except queue.Empty as exc:
                raise TimeoutError("whoami timed out") from exc
            if line is None:
                raise EOFError("backend exited")
            s = line.strip()
            if not s.startswith("{"):
                continue
            try:
                msg = json.loads(s)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == want_id:
                return msg

    try:
        deadline = time.monotonic() + VERIFY_TIMEOUT
        send(
            {
                "jsonrpc": "2.0",
                "id": "init",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "fb-session-verify", "version": "1.0"},
                },
            }
        )
        wait_for("init", deadline)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(
            {
                "jsonrpc": "2.0",
                "id": "who",
                "method": "tools/call",
                "params": {"name": "whoami", "arguments": {}},
            }
        )
        resp = wait_for("who", deadline)
    except (TimeoutError, EOFError, OSError) as exc:
        return {"authenticated": False, "name_present": False, "detail": str(exc)}
    finally:
        try:
            proc.terminate()
        except OSError:
            pass
    return _interpret_whoami(resp)


def _interpret_whoami(resp: dict) -> dict:
    """Turn a whoami tools/call response into an auth verdict (no value leaks)."""
    result = resp.get("result") or {}
    if result.get("isError"):
        text = _first_text(result)
        return {"authenticated": False, "name_present": False, "detail": _redact(text)}
    text = _first_text(result)
    try:
        payload = json.loads(text) if text else {}
    except json.JSONDecodeError:
        payload = {}
    uid = str(payload.get("uid") or "")
    name = str(payload.get("name") or "")
    authed = bool(uid) and uid != "0"
    # NEVER echo the uid/name text; only presence booleans + a class.
    return {
        "authenticated": authed,
        "name_present": bool(name),
        "detail": "whoami returned a uid" if authed else "whoami returned no uid",
    }


def _first_text(result: dict) -> str:
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            return item.get("text") or ""
    return ""


def _redact(text: str) -> str:
    """Keep the error CLASS/first line; drop anything that could carry a value."""
    line = (text or "").strip().splitlines()[0] if text else ""
    return line[:200]


def verify_whoami(cookies_path: str) -> dict:
    """Verify a cookies.json authenticates by calling the backend's whoami."""
    spec = _fb_spec()
    env = dict(os.environ)
    env["FB_COOKIES_PATH"] = cookies_path
    if not os.path.exists(cookies_path):
        return {
            "authenticated": False,
            "name_present": False,
            "detail": "cookies.json does not exist",
        }
    return _mcp_whoami(spec.cmd, env)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Refresh + verify Facebook cookies.")
    ap.add_argument("--out", help="cookies.json path (default: FB_COOKIES_PATH)")
    ap.add_argument("--profile", help="persistent browser profile dir")
    ap.add_argument(
        "--headless", action="store_true", help="no window (already logged in)"
    )
    ap.add_argument("--timeout", type=int, default=600, help="login wait seconds")
    ap.add_argument(
        "--verify-only", action="store_true", help="skip export; just whoami"
    )
    args = ap.parse_args(argv)

    out = args.out or default_cookies_path()

    if not args.verify_only:
        ok, marker = run_export(out, args.profile, args.headless, args.timeout)
        print(marker)
        if not ok:
            return 1

    verdict = verify_whoami(out)
    print(json.dumps({"verify": verdict, "cookies_path": out}, ensure_ascii=False))
    if verdict["authenticated"]:
        print(f"SUCCESS:fb-session authenticated -> {out}")
        return 0
    print(f"FAILED:fb-session written but NOT authenticated ({verdict['detail']})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
