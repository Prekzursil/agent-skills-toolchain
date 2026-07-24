#!/usr/bin/env python3
"""Restore selected session option IDs from session_options.json.

Usage:
  python restore_by_ids.py E01 C02 M01 F01
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
OPTS = HOME / ".crcp" / "cookie-bridge" / "session_options.json"


def kill(name: str) -> None:
    subprocess.run(
        ["taskkill", "/F", "/IM", f"{name}.exe", "/T"],
        capture_output=True,
        check=False,
    )


def restore_chromium(browser: str, session_file: Path) -> dict:
    profiles = {
        "edge": (
            ["msedge"],
            HOME / r"AppData\Local\Microsoft\Edge\User Data\Default",
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            HOME / r".crcp\cookie-bridge\profile-junctions\edge-ud",
        ),
        "chrome": (
            ["chrome"],
            HOME / r"AppData\Local\Google\Chrome\User Data\Default",
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            HOME / r".crcp\cookie-bridge\profile-junctions\chrome-ud",
        ),
        "comet": (
            ["Comet", "comet"],
            HOME / r"AppData\Local\Perplexity\Comet\User Data\Default",
            Path(r"C:\Program Files\Perplexity\Comet\Application\comet.exe"),
            None,
        ),
    }
    procs, profile, exe, junction = profiles[browser]
    for p in procs:
        kill(p)
    time.sleep(2)
    sess_dir = profile / "Sessions"
    sess_dir.mkdir(exist_ok=True)
    bak = profile / f"Sessions.bak-pick-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if not bak.exists() and sess_dir.exists():
        shutil.copytree(sess_dir, bak, dirs_exist_ok=True)
    # Clear active session files then copy chosen one as newest
    for p in list(sess_dir.glob("Session_*")) + list(sess_dir.glob("Tabs_*")):
        try:
            p.unlink()
        except OSError:
            pass
    # If source is Tabs_ also try to find sibling Session_ of similar age
    stamp = int(time.time() * 1_000_000)
    dest = sess_dir / f"{session_file.name.split('_')[0]}_{stamp}"
    shutil.copy2(session_file, dest)
    os.utime(dest, None)
    # Preferences crash restore
    pref_path = profile / "Preferences"
    if pref_path.is_file():
        pref = json.loads(pref_path.read_text(encoding="utf-8"))
        pref.setdefault("profile", {})
        pref["profile"]["exit_type"] = "Crashed"
        pref["profile"]["exited_cleanly"] = False
        pref.setdefault("session", {})
        pref["session"]["restore_on_startup"] = 1
        tmp = pref_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(pref, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        tmp.replace(pref_path)
    ud = junction if junction and junction.exists() else profile.parent
    if not exe.is_file() and browser == "edge":
        exe = Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")
    proc = subprocess.Popen(
        [
            str(exe),
            f"--user-data-dir={ud}",
            "--profile-directory=Default",
            "--restore-last-session",
            "--no-first-run",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return {"ok": True, "browser": browser, "pid": proc.pid, "restored_file": str(session_file), "dest": str(dest)}


def restore_firefox(session_file: Path) -> dict:
    kill("firefox")
    time.sleep(2)
    profile = HOME / r"AppData\Roaming\Mozilla\Firefox\Profiles\k4cy1nuq.default-release"
    dest = profile / "sessionstore.jsonlz4"
    if dest.is_file():
        shutil.copy2(dest, profile / f"sessionstore.jsonlz4.bak-{int(time.time())}")
    shutil.copy2(session_file, dest)
    user_js = profile / "user.js"
    existing = user_js.read_text(encoding="utf-8", errors="replace") if user_js.is_file() else ""
    block = (
        f'\n// CRCP pick restore {datetime.now().isoformat()}\n'
        'user_pref("browser.sessionstore.resume_session_once", true);\n'
        'user_pref("browser.startup.page", 3);\n'
    )
    user_js.write_text(existing + block, encoding="utf-8")
    exe = Path(r"C:\Program Files\Mozilla Firefox\firefox.exe")
    proc = subprocess.Popen(
        [str(exe), "-P", "default-release", "-restore"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    return {"ok": True, "browser": "firefox", "pid": proc.pid, "restored_file": str(session_file)}


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: python restore_by_ids.py E01 C02 M01 F01")
        return 2
    data = json.loads(OPTS.read_text(encoding="utf-8"))
    by_id = {o["id"]: o for o in data["options"]}
    results = []
    for oid in argv:
        oid = oid.strip().upper().rstrip(",")
        if oid not in by_id:
            results.append({"id": oid, "ok": False, "error": "unknown id"})
            continue
        o = by_id[oid]
        path = Path(o["file"])
        if not path.is_file():
            results.append({"id": oid, "ok": False, "error": "file missing"})
            continue
        if o["browser"] == "firefox":
            results.append({"id": oid, **restore_firefox(path)})
        else:
            results.append({"id": oid, **restore_chromium(o["browser"], path)})
        time.sleep(2)
    print(json.dumps(results, indent=2))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
