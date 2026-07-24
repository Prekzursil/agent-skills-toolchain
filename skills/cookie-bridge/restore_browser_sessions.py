#!/usr/bin/env python3
"""Restore pre-kill browser tab sessions after force-close inject.

Promotes the largest Session/Tabs files (usually the pre-kill ones),
marks Chromium profiles as crashed, forces Firefox resume_session_once,
then launches each browser with restore flags.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
REPORT = HOME / ".crcp" / "cookie-bridge" / "session_restore_report.json"


def _kill_browsers() -> None:
    for name in ("chrome", "msedge", "firefox", "Comet", "comet"):
        subprocess.run(
            ["taskkill", "/F", "/IM", f"{name}.exe", "/T"],
            capture_output=True,
            text=True,
            check=False,
        )
    time.sleep(3)


def promote_chromium_sessions(profile: Path, name: str) -> dict:
    sess = profile / "Sessions"
    out: dict = {"browser": name, "profile": str(profile), "ok": False}
    if not sess.is_dir():
        out["error"] = "no Sessions dir"
        return out

    tabs = sorted(sess.glob("Tabs_*"), key=lambda p: p.stat().st_size, reverse=True)
    sessions = sorted(sess.glob("Session_*"), key=lambda p: p.stat().st_size, reverse=True)
    if not tabs and not sessions:
        out["error"] = "empty Sessions"
        return out

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = profile / f"Sessions.bak-restore-{stamp}"
    if not bak.exists():
        shutil.copytree(sess, bak)
    out["backup"] = str(bak)

    best_tabs = tabs[0] if tabs else None
    best_sess = sessions[0] if sessions else None
    out["best_tabs"] = (
        {"name": best_tabs.name, "bytes": best_tabs.stat().st_size} if best_tabs else None
    )
    out["best_session"] = (
        {"name": best_sess.name, "bytes": best_sess.stat().st_size} if best_sess else None
    )

    removed: list[str] = []
    keep = set()
    if best_tabs:
        keep.add(best_tabs.resolve())
    if best_sess:
        keep.add(best_sess.resolve())
    for p in list(sess.glob("Session_*")) + list(sess.glob("Tabs_*")) + list(sess.glob("Apps_*")):
        if p.resolve() in keep:
            continue
        size = p.stat().st_size
        # Drop tiny post-inject session files that steal "latest"
        if size < 80_000:
            try:
                p.unlink()
                removed.append(p.name)
            except OSError:
                pass
    out["removed_small"] = removed

    now = time.time()
    if best_tabs:
        os.utime(best_tabs, (now, now + 2))
    if best_sess:
        os.utime(best_sess, (now, now + 1))

    pref_path = profile / "Preferences"
    if pref_path.is_file():
        pref_bak = profile / "Preferences.bak-before-session-restore"
        if not pref_bak.exists():
            shutil.copy2(pref_path, pref_bak)
        pref = json.loads(pref_path.read_text(encoding="utf-8"))
        pref.setdefault("profile", {})
        pref["profile"]["exit_type"] = "Crashed"
        pref["profile"]["exited_cleanly"] = False
        pref.setdefault("session", {})
        pref["session"]["restore_on_startup"] = 1  # open last session
        tmp = pref_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(pref, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(pref_path)
        out["preferences_patched"] = True

    out["ok"] = True
    return out


def promote_firefox(profile: Path) -> dict:
    out: dict = {"browser": "firefox", "profile": str(profile), "ok": False}
    backups = profile / "sessionstore-backups"
    candidates = [
        p
        for p in (
            backups / "recovery.jsonlz4",
            backups / "recovery.baklz4",
            backups / "previous.jsonlz4",
        )
        if p.is_file()
    ]
    if not candidates:
        out["error"] = "no recovery session"
        return out
    best = max(candidates, key=lambda p: p.stat().st_size)
    dest = profile / "sessionstore.jsonlz4"
    if dest.is_file():
        shutil.copy2(dest, profile / f"sessionstore.jsonlz4.bak-{int(time.time())}")
    shutil.copy2(best, dest)
    out["restored_from"] = best.name
    out["bytes"] = best.stat().st_size

    user_js = profile / "user.js"
    existing = user_js.read_text(encoding="utf-8", errors="replace") if user_js.is_file() else ""
    block = (
        f"\n// CRCP session restore {datetime.now().isoformat()}\n"
        'user_pref("browser.sessionstore.resume_session_once", true);\n'
        'user_pref("browser.sessionstore.resume_from_crash", true);\n'
        'user_pref("browser.startup.page", 3);\n'
    )
    if "CRCP session restore" not in existing:
        user_js.write_text(existing + block, encoding="utf-8")
    out["ok"] = True
    return out


def launch_browsers() -> list[dict]:
    launches: list[dict] = []
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    edge = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    if not edge.is_file():
        edge = Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
    comet = Path(r"C:\Program Files\Perplexity\Comet\Application\comet.exe")
    firefox = Path(r"C:\Program Files\Mozilla Firefox\firefox.exe")

    chrome_ud = HOME / r"AppData\Local\Google\Chrome\User Data"
    edge_ud = HOME / r"AppData\Local\Microsoft\Edge\User Data"
    comet_ud = HOME / r"AppData\Local\Perplexity\Comet\User Data"
    # Prefer junction if present (same data)
    chrome_j = HOME / r".crcp\cookie-bridge\profile-junctions\chrome-ud"
    edge_j = HOME / r".crcp\cookie-bridge\profile-junctions\edge-ud"
    if chrome_j.exists():
        chrome_ud = chrome_j
    if edge_j.exists():
        edge_ud = edge_j

    plans = [
        (
            "chrome",
            chrome,
            [
                f"--user-data-dir={chrome_ud}",
                "--profile-directory=Default",
                "--restore-last-session",
                "--no-first-run",
            ],
        ),
        (
            "edge",
            edge,
            [
                f"--user-data-dir={edge_ud}",
                "--profile-directory=Default",
                "--restore-last-session",
                "--no-first-run",
            ],
        ),
        (
            "comet",
            comet,
            [
                f"--user-data-dir={comet_ud}",
                "--profile-directory=Default",
                "--restore-last-session",
                "--no-first-run",
            ],
        ),
        (
            "firefox",
            firefox,
            [
                "-P",
                "default-release",
                "-restore",
            ],
        ),
    ]
    for name, exe, args in plans:
        if not exe.is_file():
            launches.append({"browser": name, "ok": False, "error": f"missing {exe}"})
            continue
        proc = subprocess.Popen(
            [str(exe), *args],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        launches.append({"browser": name, "ok": True, "pid": proc.pid, "args": args})
        time.sleep(2)
    return launches


def main() -> int:
    # SAFETY GATE (added 2026-07-24). This script force-kills chrome/msedge/comet/
    # firefox with `taskkill /F` as its FIRST action, BEFORE it snapshots anything.
    # Un-gated, it destroyed browser state when invoked (even with --help). It now
    # refuses unless the same env gate its sibling inject_all_main_profiles.py uses
    # is set, and --help never kills.
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(
            "restore_browser_sessions.py — force-closes ALL browsers, promotes the largest\n"
            "pre-kill Tabs/Session files, and relaunches with --restore-last-session.\n\n"
            "DANGER: force-kills chrome/msedge/comet/firefox BEFORE it snapshots. Never run\n"
            "by accident. It also kills a browser you may want left alone (e.g. Chrome).\n\n"
            "To run it intentionally, set the gate first:\n"
            "    $env:I_ACCEPT_PROFILE_RISK=1   (PowerShell)\n"
            "    set I_ACCEPT_PROFILE_RISK=1    (cmd)\n"
        )
        return 0
    if os.environ.get("I_ACCEPT_PROFILE_RISK") != "1":
        print(
            "REFUSED: restore_browser_sessions.py force-kills ALL browsers before it "
            "snapshots.\nNo browser was touched. Set I_ACCEPT_PROFILE_RISK=1 to proceed, "
            "or run with --help.",
            file=sys.stderr,
        )
        return 2
    print("Killing browsers…")
    _kill_browsers()

    results = [
        promote_chromium_sessions(
            HOME / r"AppData\Local\Google\Chrome\User Data\Default", "chrome"
        ),
        promote_chromium_sessions(
            HOME / r"AppData\Local\Microsoft\Edge\User Data\Default", "edge"
        ),
        promote_chromium_sessions(
            HOME / r"AppData\Local\Perplexity\Comet\User Data\Default", "comet"
        ),
        promote_firefox(
            HOME / r"AppData\Roaming\Mozilla\Firefox\Profiles\k4cy1nuq.default-release"
        ),
    ]
    print(json.dumps(results, indent=2))

    print("Launching with session restore…")
    launches = launch_browsers()
    report = {
        "at": datetime.now().isoformat(),
        "promote": results,
        "launches": launches,
        "notes": [
            "Chromium restore uses largest Tabs/Session files + exit_type=Crashed + --restore-last-session",
            "If a window opens empty, use History → recently closed windows (Ctrl+Shift+T repeatedly)",
            "Firefox uses sessionstore.jsonlz4 from recovery.jsonlz4 + startup.page=3",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {REPORT}")
    ok = all(r.get("ok") for r in results) and all(l.get("ok") for l in launches)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
