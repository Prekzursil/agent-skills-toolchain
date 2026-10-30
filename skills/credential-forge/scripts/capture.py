#!/usr/bin/env python3
"""capture.py -- credential-forge capability (4): browser-assisted OAuth
capture ladder (references/oauth-flows.md), in STRICT preference order with
owner-in-the-loop gates.

Ladder:
  (a) DEVICE-CODE first wherever the IdP offers it -- the owner types the code
      themselves; the automation never sees credentials.
  (b) SSO-COOKIE via env-held credentials POSTed to the portal
      (institutional-literature-access recipe; owner-sanctioned; no bot-wall).
  (c) browser-attach consent-click LAST resort only -- owner-initiated,
      owner-visible, own-accounts-only, shelling out to python playwright
      (attach MCP tools are not mounted in workflow subagents).

ANTI-PHISHING-EQUIVALENCE RULE (verbatim doctrine): silent consent-click
automation in a logged-in real profile is functionally an OAuth-phishing kit.
Owner's-own-accounts, owner-initiated, owner-visible only.

HARD REFUSALS (exit 3): never automate accounts.google.com (6 accounts,
lockout risk, zero verified wins); never headless capture against
Cloudflare/Akamai-fronted IdPs (proven dead); never extract httpOnly cookies
via attach (cookie-bridge phone-side lane owns that); cdp-endpoint fallback
stays OFF; Firefox lane impossible.

Examples:
  python capture.py --list
  python capture.py --provider entra-device            # steps only, no network
  python capture.py --provider google-oauth            # refused, exit 3
  python capture.py --provider entra-device --owner-present --tenant <id> --client-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _common as C  # noqa: E402

EXIT_REFUSED = 3

PROVIDERS = {
    "entra-device": {
        "lane": "device-code",
        "rank": "a",
        "notes": "Entra device-code endpoint verified live 2026-10-22 (HTTP 200, expires_in 900, poll 5s).",
    },
    "gcloud-device": {
        "lane": "device-code",
        "rank": "a",
        "notes": "gcloud auth login --no-launch-browser; owner completes in their own terminal.",
    },
    "gh-web": {
        "lane": "device-code",
        "rank": "a",
        "notes": "gh auth login --web; gh owns its own store refresh.",
    },
    "sso-cookie": {
        "lane": "sso-cookie",
        "rank": "b",
        "notes": "institutional portal POST from env-held credentials; owner-sanctioned.",
    },
    "browser-attach": {
        "lane": "attach",
        "rank": "c-last-resort",
        "notes": "owner-initiated + owner-visible; shells out to python playwright; httpOnly stays OFF-limits.",
    },
    # ---- hard refusals -------------------------------------------------
    "google-oauth": {
        "lane": "refused",
        "rank": "-",
        "notes": "HARD NO: never automate accounts.google.com (6 accounts, lockout risk, zero verified wins).",
    },
    "cloudflare-fronted": {
        "lane": "refused",
        "rank": "-",
        "notes": "HARD NO: headless OAuth/cookie capture against Cloudflare/Akamai-fronted IdPs is proven dead.",
    },
    "cdp-attach": {
        "lane": "refused",
        "rank": "-",
        "notes": "HARD NO: cdp-endpoint fallback stays OFF.",
    },
    "firefox-lane": {
        "lane": "refused",
        "rank": "-",
        "notes": "HARD NO: Firefox lane impossible on this box.",
    },
}


def refuse(provider: str) -> int:
    print("REFUSED: --provider %s" % provider)
    print("reason: %s" % PROVIDERS[provider]["notes"])
    print(
        "policy: references/oauth-flows.md hard walls; owner's-own-accounts scope only."
    )
    return EXIT_REFUSED


def _post_form(url: str, form: dict, headers: dict | None = None, timeout: int = 30):
    body = urllib.parse.urlencode(form).encode()
    hdr = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdr, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8", "replace"),
                dict(resp.headers),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace"), dict(exc.headers)


def run_entra_device(args) -> int:
    tenant = args.tenant or "organizations"
    device_ep = "https://login.microsoftonline.com/%s/oauth2/v2.0/devicecode" % tenant
    token_ep = "https://login.microsoftonline.com/%s/oauth2/v2.0/token" % tenant
    print("entra device-code lane (ladder rank a).")
    print("steps the OWNER performs:")
    print("  1. this tool prints a user code after you pass --owner-present")
    print(
        "  2. owner opens login.microsoft.com/devicelogin and types the code themselves"
    )
    print(
        "  3. this tool polls the token endpoint (interval from response, expires_in 900)"
    )
    print("endpoints: device=%s" % device_ep)
    if not args.owner_present:
        print(
            "DRY: no network activity without --owner-present (owner-in-the-loop gate)."
        )
        return 0
    if args.dry:
        print("DRY: --owner-present given but --dry set; plan only, no network.")
        return 0
    if not (args.client_id and args.scope):
        print(
            "FAIL: --client-id and --scope are required for a live device-code request"
        )
        return 2
    status, body, _hdrs = _post_form(
        device_ep, {"client_id": args.client_id, "scope": args.scope}
    )
    if status != 200:
        print("FAIL: devicecode endpoint HTTP %d" % status)
        return 1
    doc = json.loads(body)
    user_code = doc.get("user_code", "")
    device_code = doc.get("device_code", "")
    interval = int(doc.get("interval", 5))
    expires_in = int(doc.get("expires_in", 900))
    verification = doc.get("verification_uri", "login.microsoft.com/devicelogin")
    if not (user_code and device_code):
        print("FAIL: devicecode response missing fields (keys: %s)" % sorted(doc))
        return 1
    # user_code is MEANT to be shown to the owner; device_code is never printed.
    print("OWNER ACTION: open %s and enter code: %s" % (verification, user_code))
    print(
        "polling every %ds for up to %ds (device_code withheld from output)"
        % (interval, expires_in)
    )
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        time.sleep(interval)
        status, body, _hdrs = _post_form(
            token_ep,
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "client_id": args.client_id,
                "device_code": device_code,
            },
        )
        try:
            doc = json.loads(body)
        except ValueError:
            doc = {}
        if status == 200 and doc.get("access_token"):
            access = doc.get("access_token", "")
            refresh = doc.get("refresh_token", "")
            print(
                "capture OK: access_len=%d refresh_len=%d exp=%s"
                % (len(access), len(refresh), C.jwt_exp_iso(access) or "?")
            )
            if args.sink == "env":
                name = "ENTRA_OAUTH_ACCESS__%s" % (args.account_tag or "device")
                if args.apply:
                    ok = C.env_set_value(name, access)
                    if refresh:
                        ok = ok and C.env_set_value(
                            "ENTRA_OAUTH_REFRESH__%s" % (args.account_tag or "device"),
                            refresh,
                        )
                    print("env sink: %s -> %s" % (name, "set" if ok else "FAILED"))
                else:
                    print("env sink dry-run: would set %s (+refresh if present)" % name)
            return 0
        err = doc.get("error", "")
        if err == "authorization_pending":
            continue
        if err in ("slow_down",):
            interval = min(interval + 5, 30)
            continue
        if err in ("authorization_declined", "expired_token", "bad_verification_code"):
            print("FAIL: device flow ended: %s" % err)
            return 1
        print("FAIL: token poll HTTP %d error=%s" % (status, err or "?"))
        return 1
    print("FAIL: device code expired after %ds" % expires_in)
    return 1


def run_cli_handoff(args, command: list[str], store: str) -> int:
    print(
        "%s lane (ladder rank a): the OWNING CLI refreshes its own store (%s)."
        % (store, store)
    )
    print("owner command (run it yourself in a terminal):")
    print("  " + " ".join(command))
    if not args.owner_present:
        print("DRY: this driver does not spawn the CLI without --owner-present.")
        return 0
    if args.dry:
        print("DRY: --owner-present given but --dry set; plan only, nothing spawned.")
        return 0
    import subprocess

    try:
        proc = subprocess.run(command)
    except OSError as exc:
        print("FAIL: spawn %s: %s" % (command[0], type(exc).__name__))
        return 1
    print(
        "CLI exited %d; store mtime evidence is re-checked by lifecycle.py ledger build"
        % proc.returncode
    )
    return proc.returncode


def run_sso_cookie(args) -> int:
    missing = [n for n in (args.user_env, args.pass_env) if not n]
    if missing or not args.url:
        print("FAIL: sso-cookie needs --url --user-env NAME --pass-env NAME")
        return 2
    print(
        "sso-cookie lane (ladder rank b): POST to %s with env-held credentials."
        % args.url
    )
    print(
        "credential env NAMES: %s / %s (values read into memory only)"
        % (args.user_env, args.pass_env)
    )
    if not args.owner_present:
        print("DRY: no network without --owner-present (owner-sanctioned gate).")
        return 0
    if args.dry:
        print("DRY: --owner-present given but --dry set; plan only, no network.")
        return 0
    user = os.environ.get(args.user_env, "")
    pw = os.environ.get(args.pass_env, "")
    if not (user and pw):
        print("FAIL: %s/%s not present in process env" % (args.user_env, args.pass_env))
        return 1
    status, body, hdrs = _post_form(
        args.url, {"username": user, "password": pw, "remember": "true"}
    )
    raw_cookies = hdrs.get("Set-Cookie") or hdrs.get("set-cookie") or ""
    cookie_names = [
        part.split("=", 1)[0].strip() for part in raw_cookies.split(",") if "=" in part
    ]
    print(
        "sso POST: HTTP %d, set-cookie names: %s (values withheld)"
        % (status, ",".join(filter(None, cookie_names)) or "-")
    )
    return 0 if status in (200, 302) else 1


def run_browser_attach(args) -> int:
    print("browser-attach lane (ladder rank c-LAST-resort).")
    print(
        "conditions encoded: owner-initiated, owner-visible, own-accounts-only, "
        "no device flow available, no bot-wall, httpNow OFF-limits."
    )
    print(
        "hand-off (attach MCP tools are NOT mounted in workflow subagents; "
        "this driver shells out to python playwright):"
    )
    print(
        "  python -m playwright codegen --browser chromium  # owner drives; consent click is the OWNER's act"
    )
    print(
        "first per-client extension connect (tab-drag) and first rail sign-in are owner acts."
    )
    if not (args.owner_present and args.i_consent):
        print(
            "DRY: requires BOTH --owner-present AND --i-consent to do anything beyond this hand-off."
        )
        return 0
    if args.dry:
        print("DRY: gates passed but --dry set; nothing spawned.")
        return 0
    print(
        "FAIL: live attach automation is intentionally not implemented in this driver; "
        "run the playwright hand-off yourself (anti-phishing-equivalence rule)."
    )
    return 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="capture.py",
        description="OAuth capture ladder driver (device-code > sso-cookie > owner-visible attach); "
        "hard refusals encoded as policy",
        epilog="See references/oauth-flows.md for per-IdP verdicts and hard walls.",
    )
    ap.add_argument(
        "--list", action="store_true", help="list providers and their lane policy"
    )
    ap.add_argument(
        "--provider", choices=sorted(PROVIDERS), help="provider/lane to drive"
    )
    ap.add_argument(
        "--owner-present",
        action="store_true",
        help="GATE: confirms the owner is present and initiating (required for any network/spawn)",
    )
    ap.add_argument(
        "--i-consent",
        action="store_true",
        help="GATE: explicit owner consent for the attach lane",
    )
    ap.add_argument(
        "--dry", action="store_true", help="plan only; no network, no spawn, no writes"
    )
    # entra-device options
    ap.add_argument("--tenant", help="Entra tenant id or 'organizations'")
    ap.add_argument("--client-id", help="OAuth client id for the device-code request")
    ap.add_argument("--scope", help="OAuth scope string for the device-code request")
    ap.add_argument(
        "--account-tag", help="account tag for env sink names (<BASE>__<account>)"
    )
    ap.add_argument(
        "--sink",
        choices=["none", "env"],
        default="none",
        help="optional sink for captured tokens",
    )
    ap.add_argument(
        "--apply", action="store_true", help="required for a live env sink write"
    )
    # sso-cookie options
    ap.add_argument("--url", help="portal URL for the sso-cookie POST")
    ap.add_argument("--user-env", help="env NAME holding the portal username")
    ap.add_argument("--pass-env", help="env NAME holding the portal password")
    args = ap.parse_args(argv)
    if args.list:
        for name in sorted(PROVIDERS):
            p = PROVIDERS[name]
            print(
                "%-18s rank=%-14s lane=%-10s %s"
                % (name, p["rank"], p["lane"], p["notes"])
            )
        return 0
    if not args.provider:
        ap.print_usage()
        print("FAIL: --provider required (or --list)")
        return 2
    spec = PROVIDERS[args.provider]
    if spec["lane"] == "refused":
        return refuse(args.provider)
    if args.provider == "entra-device":
        return run_entra_device(args)
    if args.provider == "gcloud-device":
        return run_cli_handoff(
            args, ["gcloud", "auth", "login", "--no-launch-browser"], "gcloud"
        )
    if args.provider == "gh-web":
        return run_cli_handoff(args, ["gh", "auth", "login", "--web"], "gh")
    if args.provider == "sso-cookie":
        return run_sso_cookie(args)
    if args.provider == "browser-attach":
        return run_browser_attach(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
