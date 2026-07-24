#!/usr/bin/env python3
"""Safe restore of signed-in account lists + Preferences from Jul 20-21 baks.

ONLY uses:
  Preferences.bak-before-session-restore  (per browser Default profile)

EXPLICITLY IGNORES:
  .sso-mirror-backup-*  (Jul 7-8 — owner said leave alone)

Does NOT touch:
  History, Login Data, Bookmarks, Cookies, Sessions (unless --also-sessions later)

Usage:
  python safe_restore_prefs_accounts.py --dry-run
  python safe_restore_prefs_accounts.py --apply
  python safe_restore_prefs_accounts.py --apply --browsers chrome,edge,comet

Requires all target browsers fully quit.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path.home() / ".crcp" / "cookie-bridge"
LOCAL = Path(os.environ.get("LOCALAPPDATA", ""))

BROWSERS: dict[str, dict[str, Path]] = {
    "chrome": {
        "default": LOCAL / r"Google\Chrome\User Data\Default",
        "process": "chrome",
    },
    "edge": {
        "default": LOCAL / r"Microsoft\Edge\User Data\Default",
        "process": "msedge",
    },
    "comet": {
        "default": LOCAL / r"Perplexity\Comet\User Data\Default",
        "process": "Comet",
    },
}

BAK_NAME = "Preferences.bak-before-session-restore"
LIVE_NAME = "Preferences"


def process_running(name: str) -> bool:
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {name}.exe", "/NH"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    out = (r.stdout or "").lower()
    return f"{name.lower()}.exe" in out


def account_key(a: dict[str, Any]) -> str:
    return str(a.get("account_id") or a.get("email") or json.dumps(a, sort_keys=True)[:80])


def list_accounts(pref: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for a in pref.get("account_info") or []:
        if not isinstance(a, dict):
            continue
        out.append(
            {
                "account_id": str(a.get("account_id") or ""),
                "email": str(a.get("email") or ""),
                "full_name": str(a.get("full_name") or ""),
            }
        )
    return out


def merge_account_info(live: dict[str, Any], bak: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Union account_info by account_id/email; prefer bak entry when both exist (richer pre-break)."""
    live_list = [a for a in (live.get("account_info") or []) if isinstance(a, dict)]
    bak_list = [a for a in (bak.get("account_info") or []) if isinstance(a, dict)]

    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    # bak first (pre-break accounts)
    for a in bak_list:
        k = account_key(a)
        if k not in merged:
            order.append(k)
        merged[k] = a
    # add live-only accounts
    for a in live_list:
        k = account_key(a)
        if k not in merged:
            order.append(k)
            merged[k] = a

    new_live = dict(live)
    new_live["account_info"] = [merged[k] for k in order]

    # Optional: restore signin.accounts_metadata_dict keys from bak if live missing
    live_signin = dict(live.get("signin") or {})
    bak_signin = bak.get("signin") or {}
    if isinstance(bak_signin, dict):
        bak_meta = bak_signin.get("accounts_metadata_dict")
        live_meta = live_signin.get("accounts_metadata_dict")
        if isinstance(bak_meta, dict):
            if not isinstance(live_meta, dict):
                live_signin["accounts_metadata_dict"] = bak_meta
            else:
                # union keys
                m = dict(live_meta)
                for k, v in bak_meta.items():
                    if k not in m:
                        m[k] = v
                live_signin["accounts_metadata_dict"] = m
        new_live["signin"] = live_signin

    stats = {
        "live_before": list_accounts(live),
        "bak": list_accounts(bak),
        "live_after": list_accounts(new_live),
        "added_emails": sorted(
            {
                a["email"]
                for a in list_accounts(new_live)
                if a["email"]
                and a["email"] not in {x["email"] for x in list_accounts(live) if x["email"]}
            }
        ),
    }
    return new_live, stats


def handle_browser(name: str, *, apply: bool, backup_root: Path) -> dict[str, Any]:
    cfg = BROWSERS[name]
    default = cfg["default"]
    live_p = default / LIVE_NAME
    bak_p = default / BAK_NAME
    proc = cfg["process"]

    report: dict[str, Any] = {
        "browser": name,
        "default": str(default),
        "live": str(live_p),
        "bak": str(bak_p),
    }

    if not default.is_dir():
        report["ok"] = False
        report["error"] = "profile_missing"
        return report
    if not live_p.is_file():
        report["ok"] = False
        report["error"] = "live_preferences_missing"
        return report
    if not bak_p.is_file():
        report["ok"] = False
        report["error"] = "bak_missing"
        report["note"] = f"no {BAK_NAME} — nothing to restore for accounts"
        return report

    running = process_running(proc)
    report["process_running"] = running

    # Read is OK while browser is open; write is not.
    try:
        live = json.loads(live_p.read_text(encoding="utf-8"))
        bak = json.loads(bak_p.read_text(encoding="utf-8"))
    except Exception as exc:
        report["ok"] = False
        report["error"] = f"read_fail:{type(exc).__name__}:{exc}"
        return report

    merged, stats = merge_account_info(live, bak)
    report["stats"] = stats
    report["bak_mtime"] = datetime.fromtimestamp(bak_p.stat().st_mtime).isoformat()
    report["live_mtime"] = datetime.fromtimestamp(live_p.stat().st_mtime).isoformat()

    if not stats["added_emails"] and len(stats["live_before"]) >= len(stats["bak"]):
        report["ok"] = True
        report["action"] = "noop_live_already_has_all_or_more"
        return report

    if not apply:
        report["ok"] = True
        report["action"] = "dry_run_would_merge"
        if running:
            report["hint"] = f"Quit {proc}.exe before --apply"
        return report

    if running:
        report["ok"] = False
        report["error"] = f"process_running:{proc}.exe"
        report["hint"] = "Fully quit the browser (Task Manager) then re-run --apply"
        return report

    bdir = backup_root / name
    bdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_p, bdir / "Preferences.live-before")
    sec = default / "Secure Preferences"
    if sec.is_file():
        shutil.copy2(sec, bdir / "Secure Preferences.live-before")

    tmp = live_p.with_suffix(".tmp-restore")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(live_p)

    report["ok"] = True
    report["action"] = "merged_account_info"
    report["backup_dir"] = str(bdir)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Safe Jul20-21 Preferences account merge restore")
    p.add_argument("--dry-run", action="store_true", help="Report only (default if no --apply)")
    p.add_argument("--apply", action="store_true", help="Write merged Preferences (browsers must be quit)")
    p.add_argument(
        "--browsers",
        default="chrome,edge,comet",
        help="comma list: chrome,edge,comet",
    )
    args = p.parse_args(argv)
    apply = bool(args.apply)
    if not apply:
        args.dry_run = True

    names = [x.strip() for x in args.browsers.split(",") if x.strip()]
    for n in names:
        if n not in BROWSERS:
            print(f"Unknown browser: {n}", file=sys.stderr)
            return 2

    # Refuse apply if any selected browser running
    if apply:
        busy = [n for n in names if process_running(BROWSERS[n]["process"])]
        if busy:
            print("REFUSED: browsers still running:", ", ".join(busy))
            print("Quit them fully, then re-run with --apply")
            return 3

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = STORE / f"pre-restore-{stamp}"
    if apply:
        backup_root.mkdir(parents=True, exist_ok=True)

    print("Mode:", "APPLY" if apply else "DRY-RUN")
    print("Ignoring: .sso-mirror-backup-* (Jul 7-8)")
    print("Source bak:", BAK_NAME)
    print()

    results = []
    for n in names:
        r = handle_browser(n, apply=apply, backup_root=backup_root)
        results.append(r)
        print(f"--- {n} ---")
        print("  action:", r.get("action") or r.get("error"))
        st = r.get("stats") or {}
        if st:
            print("  accounts LIVE before:", [a.get("email") for a in st.get("live_before") or []])
            print("  accounts BAK:        ", [a.get("email") for a in st.get("bak") or []])
            print("  accounts after:      ", [a.get("email") for a in st.get("live_after") or []])
            print("  would add:           ", st.get("added_emails"))
        if r.get("error"):
            print("  error:", r["error"], r.get("hint") or "")
        print()

    report = {
        "at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "dry_run",
        "ignored": ["sso-mirror-backup-20260707", "sso-mirror-backup-20260708"],
        "results": results,
        "backup_root": str(backup_root) if apply else None,
    }
    out = STORE / f"safe_restore_report_{stamp}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Report:", out)
    if apply:
        print("Backups of LIVE prefs:", backup_root)
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
