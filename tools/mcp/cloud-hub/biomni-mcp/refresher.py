#!/usr/bin/env python3
"""Biomni refresh-at-source broker — keep the Bearer fresh, hands-off, via a browser profile.

The companion to ``broker.py``. Phylo's WorkOS session keeps its refresh token in an
HttpOnly cookie and rotates it (one-time-use), so a copied refresh token can't be
shared — the ONLY stable way to keep a fresh Bearer without a human each time is to
let a browser that OWNS the session mint it. This does exactly that:

  * ``login``  — launch a HEADED browser with a PERSISTED profile; YOU sign in once.
                 The session cookie lives in the profile from then on.
  * ``refresh``— launch that profile HEADLESS, let the app mint a fresh Bearer, capture
                 it from the ``api.phylo.bio`` ``Authorization`` header, and write it to
                 the broker's store (a chmod-600 file or the OS keyring).
  * ``watch``  — ``refresh`` on a loop (also keeps the WorkOS session sliding-alive).

``broker.py`` then serves that stored token to the connector, which holds none. The
token flows browser -> this process -> store, entirely LOCAL; it is never printed
(masked only) and never enters the connector, the hub, or an agent's context. YOU do
the one-time sign-in; nothing here handles a password.

Requires Playwright:  ``pip install playwright`` then ``playwright install chromium``.

Examples:
  python refresher.py login                       # sign in once (headed)
  python refresher.py refresh                     # one fresh token -> ~/.biomni-mcp/broker_token
  python refresher.py watch --interval 1800       # keep it fresh every 30 min
  python refresher.py refresh --profile ~/.biomni-mcp/profiles/andrei --out-keyring biomni:andrei
"""

from __future__ import annotations

import argparse
import os
import sys
import time

WEB_URL = "https://biomni.phylo.bio"
API_HOST = "api.phylo.bio"
SIGNIN_HOST = "signin.phylo.bio"
CAPTURE_TIMEOUT_MS = 45_000
LOGIN_TIMEOUT_MS = 300_000  # 5 min for the human to finish signing in


def _default_profile() -> str:
    return os.path.join(os.path.expanduser("~"), ".biomni-mcp", "profiles", "default")


def _default_store_file() -> str:
    return os.path.join(os.path.expanduser("~"), ".biomni-mcp", "broker_token")


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested; no browser)
# --------------------------------------------------------------------------- #
def _mask(token: str) -> str:
    """Non-reversible preview; never the full value."""
    if not token:
        return ""
    return f"...{token[-4:]}" if len(token) > 8 else "set"


def bearer_from_auth_header(value: str) -> str:
    """Extract the token from an ``Authorization: Bearer <token>`` value; "" otherwise."""
    if not isinstance(value, str):
        return ""
    parts = value.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
        return parts[1].strip()
    return ""


def select_bearer(captured: list[str]) -> str:
    """Pick the best Bearer from captured Authorization headers (longest wins)."""
    tokens = [bearer_from_auth_header(v) for v in captured]
    tokens = [t for t in tokens if t]
    return max(tokens, key=len) if tokens else ""


def write_token(store: dict, token: str) -> str:
    """Write the token to the configured store; return a human status. Never logs it."""
    if store["kind"] == "file":
        _write_token_file(store["path"], token)
        return f"wrote token ({_mask(token)}) -> file {store['path']} (chmod 600)"
    if store["kind"] == "keyring":
        import keyring  # noqa: PLC0415  (optional dep, lazy)

        keyring.set_password(store["service"], store["user"], token)
        return (
            f"wrote token ({_mask(token)}) -> keyring "
            f"{store['service']}:{store['user']}"
        )
    raise ValueError(f"unknown store kind {store['kind']!r}")


def _write_token_file(path: str, token: str) -> None:
    """Atomically write the token with restrictive (0600) permissions."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(token)
    os.replace(tmp, path)
    try:  # best-effort lockdown (Windows honours only the read-only bit)
        os.chmod(path, 0o600)
    except OSError:
        pass


def resolve_store(args) -> dict:
    """Build the store spec from CLI args (file default, or keyring)."""
    if getattr(args, "out_keyring", ""):
        service, _, user = args.out_keyring.partition(":")
        return {"kind": "keyring", "service": service, "user": user or "biomni"}
    return {"kind": "file", "path": args.out_file or _default_store_file()}


# --------------------------------------------------------------------------- #
# Playwright shell (lazy import; not unit-tested — needs a real browser)
# --------------------------------------------------------------------------- #
def _playwright():
    """Import Playwright lazily; return (module, error_hint)."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        return None, (
            "Playwright not available; `pip install playwright` then "
            f"`playwright install chromium` ({exc})"
        )
    return sync_playwright, None


def _capture_bearer(
    profile: str, url: str, headless: bool, timeout_ms: int
) -> tuple[str, str]:
    """Open ``url`` with the persisted profile, capture a fresh Bearer; (token, error)."""
    sync_playwright, err = _playwright()
    if err:
        return "", err
    captured: list[str] = []
    landed_on_signin = {"v": False}
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=profile, headless=headless
        )
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            def _on_request(req):
                if API_HOST in req.url:
                    auth = req.headers.get("authorization")
                    if auth:
                        captured.append(auth)

            page.on("request", _on_request)
            page.goto(url, timeout=60_000)
            deadline = time.monotonic() + timeout_ms / 1000.0
            while time.monotonic() < deadline:
                if select_bearer(captured):
                    break
                if SIGNIN_HOST in (page.url or ""):
                    landed_on_signin["v"] = True
                    if not headless:  # login mode: keep waiting for the human
                        pass
                    else:
                        break
                page.wait_for_timeout(1000)
        finally:
            ctx.close()
    token = select_bearer(captured)
    if token:
        return token, ""
    if landed_on_signin["v"]:
        return "", (
            "not signed in for this profile (redirected to signin.phylo.bio) — run "
            "`refresher.py login` and complete sign-in in the browser."
        )
    return "", "no api.phylo.bio Authorization header seen before timeout"


def cmd_login(args) -> int:
    """Headed sign-in: launch the persisted profile so the user authenticates once."""
    print(
        f"[refresher] opening {args.url} (headed) — sign in; capture completes on success."
    )
    token, err = _capture_bearer(
        args.profile, args.url, headless=False, timeout_ms=LOGIN_TIMEOUT_MS
    )
    if err:
        print(f"[refresher] login incomplete: {err}", file=sys.stderr)
        return 1
    print(
        f"[refresher] signed in; session saved to profile {args.profile} ({_mask(token)})."
    )
    print("[refresher] you can now run `refresh` / `watch` headless.")
    return 0


def cmd_refresh(args) -> int:
    """Headless one-shot: capture a fresh Bearer and write it to the store."""
    store = resolve_store(args)
    token, err = _capture_bearer(
        args.profile, args.url, headless=True, timeout_ms=args.timeout_ms
    )
    if err:
        print(f"[refresher] refresh failed: {err}", file=sys.stderr)
        return 1
    print(f"[refresher] {write_token(store, token)}")
    return 0


def cmd_watch(args) -> int:
    """Loop ``refresh`` every ``--interval`` seconds (keeps the session sliding-alive)."""
    store = resolve_store(args)
    print(f"[refresher] watching: refresh every {args.interval}s -> {store['kind']}")
    while True:
        token, err = _capture_bearer(
            args.profile, args.url, headless=True, timeout_ms=args.timeout_ms
        )
        if err:
            print(f"[refresher] refresh failed (will retry): {err}", file=sys.stderr)
        else:
            print(f"[refresher] {write_token(store, token)}")
        try:
            time.sleep(max(60, args.interval))
        except KeyboardInterrupt:
            return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Biomni refresh-at-source broker (Playwright)"
    )
    ap.add_argument(
        "--profile", default=_default_profile(), help="persisted browser profile dir"
    )
    ap.add_argument("--url", default=WEB_URL, help="Biomni web app URL")
    ap.add_argument(
        "--out-file",
        default="",
        help="token store file (default ~/.biomni-mcp/broker_token)",
    )
    ap.add_argument(
        "--out-keyring", default="", help="write to OS keyring service[:user] instead"
    )
    ap.add_argument(
        "--timeout-ms", type=int, default=CAPTURE_TIMEOUT_MS, help="capture timeout"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("login", help="headed sign-in (once per profile)")
    sub.add_parser("refresh", help="headless one-shot token refresh")
    w = sub.add_parser("watch", help="headless refresh on a loop")
    w.add_argument(
        "--interval", type=int, default=1800, help="seconds between refreshes"
    )
    return ap


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    if not hasattr(args, "interval"):
        args.interval = 1800
    return {"login": cmd_login, "refresh": cmd_refresh, "watch": cmd_watch}[args.cmd](
        args
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
