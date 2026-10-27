#!/usr/bin/env python3
"""TST-0067 consumer: the child process that OBSERVES, never the setter.

Prints one JSON line with the value it sees, read through TWO mechanically
independent in-child signals:
  userspace: os.environ (CRT/startup env block copy)
  winapi:    GetEnvironmentVariableW via kernel32 (live env block query)
On POSIX the second signal falls back to /proc/self/environ.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def read_env_userspace(key: str):
    return os.environ.get(key)


def read_env_winapi(key: str):
    if os.name == "nt":
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetEnvironmentVariableW(key, buf, 1024)
        return buf.value if n else None
    raw = Path("/proc/self/environ").read_bytes()
    for entry in raw.split(b"\0"):
        if entry.startswith(key.encode() + b"="):
            return entry.split(b"=", 1)[1].decode("utf-8", "replace")
    return None


def read_settings(path: Path, key: str):
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc.get(key)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["env", "settings"], required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--scope-file", default=None)
    args = ap.parse_args()
    if args.mode == "env":
        userspace = read_env_userspace(args.key)
        winapi = read_env_winapi(args.key)
        print(json.dumps({
            "consumer_pid": os.getpid(),
            "signals_agree": userspace == winapi,
            "userspace": userspace,
            "signal_2": winapi,
        }))
    else:
        value = read_settings(Path(args.scope_file), args.key)
        print(json.dumps({
            "consumer_pid": os.getpid(),
            "scope_file": str(args.scope_file),
            "userspace": value,
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
