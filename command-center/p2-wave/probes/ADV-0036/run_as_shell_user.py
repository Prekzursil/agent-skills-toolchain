#!/usr/bin/env python3
"""Spawn a command with the NON-ELEVATED Explorer shell token.

Canonical installer trick: the desktop shell (explorer.exe) runs at standard
integrity without the admin-group enabled even when the current console is
elevated. We duplicate explorer's token and CreateProcessWithTokenW with it,
yielding a genuinely non-elevated process on the same interactive session.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import subprocess
import sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
a32 = ctypes.WinDLL("advapi32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)

TOKEN_QUERY = 0x0008
TOKEN_DUPLICATE = 0x0002
TOKEN_ASSIGN_PRIMARY = 0x0001
TOKEN_ADJUST_DEFAULT = 0x0080
TOKEN_ADJUST_SESSIONID = 0x0100
MAX_PATH = 260


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.c_void_p), ("hStdInput", wintypes.HANDLE),
        ("hStdOutput", wintypes.HANDLE), ("hStdError", wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


def shell_token() -> wintypes.HANDLE:
    hwnd = u32.GetShellWindow()
    if not hwnd:
        raise OSError("no shell window")
    pid = wintypes.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    hproc = k32.OpenProcess(0x0400, False, pid)  # PROCESS_QUERY_INFORMATION
    if not hproc:
        raise OSError(f"OpenProcess(explorer) failed {ctypes.get_last_error()}")
    tok = wintypes.HANDLE()
    if not a32.OpenProcessToken(hproc, TOKEN_QUERY | TOKEN_DUPLICATE | TOKEN_ASSIGN_PRIMARY | TOKEN_ADJUST_DEFAULT | TOKEN_ADJUST_SESSIONID, ctypes.byref(tok)):
        raise OSError(f"OpenProcessToken(explorer) failed {ctypes.get_last_error()}")
    return tok


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: run_as_shell_user.py <cmd> [args...]", file=sys.stderr)
        return 2
    try:
        tok = shell_token()
    except OSError as exc:
        print(f"shell-token: {exc}", file=sys.stderr)
        return 3
    si = STARTUPINFO()
    si.cb = ctypes.sizeof(si)
    si.lpDesktop = "winsta0\\default"
    pi = PROCESS_INFORMATION()
    cmd = subprocess.list2cmdline(sys.argv[1:])
    cmdline = ctypes.create_unicode_buffer(cmd)
    # explorer's token is an impersonation token; make it PRIMARY for
    # CreateProcessAsUser (error 1375 from CreateProcessWithTokenW otherwise).
    SecurityImpersonation = 2
    TokenPrimary = 1
    primary = wintypes.HANDLE()
    if not a32.DuplicateTokenEx(
        tok,
        0x0F01FF,  # TOKEN_ALL_ACCESS
        None,
        SecurityImpersonation,
        TokenPrimary,
        ctypes.byref(primary),
    ):
        print(f"DuplicateTokenEx failed {ctypes.get_last_error()}", file=sys.stderr)
        return 5
    if not a32.CreateProcessAsUserW(primary, None, cmdline, None, None, False, 0, None, None, ctypes.byref(si), ctypes.byref(pi)):
        print(f"CreateProcessAsUserW failed {ctypes.get_last_error()}", file=sys.stderr)
        return 4
    WAIT_INFINITE = 0xFFFFFFFF
    k32.WaitForSingleObject(pi.hProcess, WAIT_INFINITE)
    code = wintypes.DWORD()
    k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    k32.CloseHandle(pi.hProcess)
    k32.CloseHandle(pi.hThread)
    return code.value


if __name__ == "__main__":
    raise SystemExit(main())
