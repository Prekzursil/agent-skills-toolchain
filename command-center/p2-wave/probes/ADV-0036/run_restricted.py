#!/usr/bin/env python3
"""Spawn a command with a SAFER NORMALUSER (non-elevated) token and wait.

Used by ADV-0036 probe 2 so the empirical write test measures the ACL
decision a NON-ELEVATED process actually receives, even though the driving
shell happens to be elevated.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys
from ctypes import wintypes

SAFER_SCOPEID_MACHINE = 1
SAFER_LEVELID_NORMALUSER = 0x40000
SAFER_LEVEL_OPEN = 1


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_restricted.py <cmd> [args...]", file=sys.stderr)
        return 2
    sa = ctypes.WinDLL("advapi32")
    sa.SaferCreateLevel.restype = wintypes.BOOL
    sa.SaferComputeTokenFromLevel.restype = wintypes.BOOL
    sa.SaferCloseLevel.restype = wintypes.BOOL
    level = wintypes.HANDLE()
    if not sa.SaferCreateLevel(SAFER_SCOPEID_MACHINE, SAFER_LEVELID_NORMALUSER, SAFER_LEVEL_OPEN, ctypes.byref(level), None):
        print("SaferCreateLevel failed", ctypes.GetLastError(), file=sys.stderr)
        return 3
    token = wintypes.HANDLE()
    if not sa.SaferComputeTokenFromLevel(level, None, ctypes.byref(token), 0, None):
        print("SaferComputeTokenFromLevel failed", ctypes.GetLastError(), file=sys.stderr)
        return 4
    # CreateProcessWithTokenW via advapi32
    adv = ctypes.windll.advapi32
    cmd = subprocess.list2cmdline(sys.argv[1:])
    si = ctypes.create_string_buffer(104)  # STARTUPINFOW approx (68 ptr-size)
    pi = ctypes.create_string_buffer(24)
    cmdline = ctypes.create_unicode_buffer(cmd)
    ok = adv.CreateProcessWithTokenW(
        token,
        0,
        None,
        cmdline,
        0,
        None,
        None,
        ctypes.byref(si),
        ctypes.byref(pi),
    )
    if not ok:
        print("CreateProcessWithTokenW failed", ctypes.GetLastError(), file=sys.stderr)
        return 5
    PROCESS_SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0
    handle = int.from_bytes(pi[0:8], "little") if ctypes.sizeof(ctypes.c_void_p) == 8 else int.from_bytes(pi[0:4], "little")
    rc = ctypes.windll.kernel32.WaitForSingleObject(wintypes.HANDLE(handle), 120000)
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(wintypes.HANDLE(handle), ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(handle))
    sa.SaferCloseLevel(level)
    ctypes.windll.kernel32.CloseHandle(token)
    if rc != WAIT_OBJECT_0:
        print("wait failed", rc, file=sys.stderr)
        return 6
    return exit_code.value


if __name__ == "__main__":
    raise SystemExit(main())
