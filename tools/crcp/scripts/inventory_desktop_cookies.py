#!/usr/bin/env python3
"""Inventory ChatGPT Desktop Chromium cookies (metadata only — no values).

Reads the live Cookies SQLite with FILE_SHARE_READ|WRITE so the locked Desktop
DB can be snapshotted without closing ChatGPT.
"""

from __future__ import annotations

import ctypes
import json
import os
import sqlite3
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

GENERIC_READ = 0x80000000
FILE_SHARE_ALL = 0x00000001 | 0x00000002 | 0x00000004
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

AUTH_HINTS = (
    "session",
    "token",
    "auth",
    "puid",
    "cf_",
    "oai",
    "next-auth",
    "__secure",
    "__host",
    "clearance",
    "did",
)


def shared_read_bytes(path: Path) -> bytes:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateFileW = k32.CreateFileW
    CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    CreateFileW.restype = wintypes.HANDLE
    ReadFile = k32.ReadFile
    GetFileSizeEx = k32.GetFileSizeEx
    CloseHandle = k32.CloseHandle

    handle = CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_ALL,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle in (invalid, 0, 0xFFFFFFFF):
        raise OSError(f"CreateFile failed winerr={ctypes.get_last_error()} path={path}")

    size = wintypes.LARGE_INTEGER()
    if not GetFileSizeEx(handle, ctypes.byref(size)):
        err = ctypes.get_last_error()
        CloseHandle(handle)
        raise OSError(f"GetFileSizeEx failed winerr={err}")

    n = int(size.QuadPart)
    buf = (ctypes.c_char * n)()
    read = wintypes.DWORD()
    ok = ReadFile(handle, buf, n, ctypes.byref(read), None)
    CloseHandle(handle)
    if not ok:
        raise OSError(f"ReadFile failed winerr={ctypes.get_last_error()}")
    return bytes(buf[: read.value])


def chrome_expiry_to_unix(expires_utc: int | None) -> float | None:
    if not expires_utc or expires_utc <= 0:
        return None
    return expires_utc / 1_000_000 - 11_644_473_600


def main() -> int:
    src = (
        Path(os.environ["APPDATA"])
        / "Codex"
        / "web"
        / "Codex"
        / "Default"
        / "Network"
        / "Cookies"
    )
    if not src.is_file():
        print(json.dumps({"error": f"missing {src}"}))
        return 1

    raw = shared_read_bytes(src)
    tmp = Path(tempfile.gettempdir()) / "chatgpt_desktop_cookies_ro.db"
    tmp.write_bytes(raw)

    con = sqlite3.connect(f"file:{tmp.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    if "cookies" not in tables:
        print(json.dumps({"error": "no cookies table", "tables": tables, "bytes": len(raw)}))
        return 2

    rows = con.execute(
        "SELECT host_key, name, path, is_secure, is_httponly, expires_utc, samesite, "
        "has_expires, is_persistent, LENGTH(encrypted_value) AS enc_len, "
        "LENGTH(value) AS val_len FROM cookies ORDER BY host_key, name"
    ).fetchall()

    inventory = []
    auth_relevant = []
    for row in rows:
        name = row["name"] or ""
        host = row["host_key"] or ""
        auth_like = any(h in name.lower() for h in AUTH_HINTS) or any(
            d in host for d in ("chatgpt", "openai", "oaistatic")
        )
        rec = {
            "host_key": host,
            "name": name,
            "path": row["path"],
            "secure": bool(row["is_secure"]),
            "httpOnly": bool(row["is_httponly"]),
            "samesite": row["samesite"],
            "persistent": bool(row["is_persistent"]),
            "expires_unix": chrome_expiry_to_unix(row["expires_utc"]),
            "encrypted_value_len": row["enc_len"],
            "plaintext_value_len": row["val_len"],
            "auth_like": auth_like,
        }
        inventory.append(rec)
        if auth_like:
            auth_relevant.append(rec)

    report = {
        "source": str(src),
        "user_data_dir": str(src.parents[2]),
        "bytes_read": len(raw),
        "cookie_count": len(inventory),
        "auth_relevant_count": len(auth_relevant),
        "all_hosts": sorted({r["host_key"] for r in inventory}),
        "all_names": sorted({r["name"] for r in inventory}),
        "auth_relevant": auth_relevant,
        "note": "Values not exported — encrypted_value is DPAPI-bound to this machine/user.",
    }

    out = (
        Path(__file__).resolve().parents[1]
        / "reports"
        / "desktop_cookie_inventory_2026-07-20.json"
    )
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWROTE {out}", file=sys.stderr)
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
