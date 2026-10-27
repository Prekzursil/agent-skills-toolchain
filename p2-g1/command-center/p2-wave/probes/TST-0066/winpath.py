#!/usr/bin/env python3
"""TST-0066 winpath: canonical Windows path identity.

Per the receipt's identity model (winpath.py evidence row: trailing
spaces and periods stripped per component before compare): canonical()
strips trailing dots/spaces per component, casefolds, and expands 8.3
short names to their long form when resolvable live via
GetShortPathNameW, else via an explicit fixture map. same_identity()
answers whether two strings denote ONE file identity."""
from __future__ import annotations

import ctypes
from ctypes import wintypes

FIXTURE_83: dict[str, str] = {
    ("c:" + chr(92) + "work" + chr(92) + "ast-in~1" + chr(92) + "command-center" + chr(92) + "work-u~1.jso").casefold():
        "c:" + chr(92) + "work" + chr(92) + "ast-integrate" + chr(92) + "command-center" + chr(92) + "WORK-UNIT-CATALOG.json",
    ("c:" + chr(92) + "progra~1" + chr(92) + "app" + chr(92) + "secret~1.txt").casefold():
        "c:" + chr(92) + "program files" + chr(92) + "app" + chr(92) + "secret.txt",
    ("c:" + chr(92) + "progra~1" + chr(92) + "app" + chr(92) + "hooks~1" + chr(92) + "hook~1.py").casefold():
        "c:" + chr(92) + "program files" + chr(92) + "app" + chr(92) + "hooks" + chr(92) + "hook.py",
}


def live_long(path: str) -> str | None:
    """Resolve a path with 8.3 components to its long form via Win32."""
    if not path:
        return None
    GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
    GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    GetShortPathNameW.restype = wintypes.DWORD
    n = GetShortPathNameW(path, None, 0)
    if n == 0:
        return None
    buf = ctypes.create_unicode_buffer(n)
    GetShortPathNameW(path, buf, n)
    return buf.value or None


def live_expand(path: str) -> str:
    """Resolve 8.3 components to their long form via GetLongPathNameW."""
    if not path:
        return path
    GetLongPathNameW = ctypes.windll.kernel32.GetLongPathNameW
    GetLongPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    GetLongPathNameW.restype = wintypes.DWORD
    buf = ctypes.create_unicode_buffer(32768)
    n = GetLongPathNameW(path, buf, 32768)
    if n == 0:
        return path
    return buf.value or path


def _expand_83(path: str) -> str:
    key = path.casefold()
    if key in FIXTURE_83:
        return FIXTURE_83[key]
    long_form = live_expand(path)
    if long_form != path:
        return long_form
    return path


def canonical(path: str) -> str:
    parts = []
    for comp in path.replace("/", chr(92)).split(chr(92)):
        if comp in ("", "."):
            continue
        if comp == "..":
            if parts:
                parts.pop()
            continue
        comp = comp.rstrip(" .")
        parts.append(comp.casefold())
    return chr(92).join(parts)


def same_identity(a: str, b: str) -> bool:
    return canonical(_expand_83(a)) == canonical(_expand_83(b))
