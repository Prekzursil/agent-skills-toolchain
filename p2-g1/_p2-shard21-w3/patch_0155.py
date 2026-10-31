#!/usr/bin/env python3
"""Shard21 w3: port TST-0155 reader.py to Windows rename-rotation.

The CRT open() shares read/write but not delete, so os.replace(log, log.1)
raises WinError 32 while the reader holds the fd. Opening via CreateFileW
with FILE_SHARE_DELETE keeps the same open-fd semantics as POSIX and lets
rename-rotation proceed under the handle - the exact tail -F behavior the
unit tests.
"""
from pathlib import Path

P = Path.home() / "p2-g1" / "command-center" / "p2-wave" / "probes" / "TST-0155" / "reader.py"
src = P.read_text(encoding="utf-8")

helper = '''

def _open_shared_delete(path: Path):
    """Open for read with FILE_SHARE_DELETE so a rename-rotate can proceed
    while this reader keeps the fd open. The Windows CRT open shares
    read/write only, which makes os.replace raise WinError 32; POSIX open is
    unchanged. Returns a binary file object."""
    if os.name != "nt":
        return open(path, "rb")
    import ctypes
    import msvcrt

    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x1
    FILE_SHARE_WRITE = 0x2
    FILE_SHARE_DELETE = 0x4
    OPEN_EXISTING = 0x3
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    k32.CreateFileW.restype = ctypes.c_void_p
    handle = k32.CreateFileW(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError(f"CreateFileW failed for {path} (err={ctypes.GetLastError()})")
    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY | getattr(os, "O_BINARY", 0))
    return os.fdopen(fd, "rb")
'''

anchor = '''def complete_lines(blob: bytes) -> tuple[list[str], bytes]:'''
assert anchor in src
src = src.replace(anchor, helper.strip("\n") + "\n\n\n" + anchor, 1)

# FollowReader._open_path
old = '''    def _open_path(self, start: int = 0) -> None:
        self.close()
        self.fp = open(self.path, "rb")
        if start:
            self.fp.seek(start)
        self.ident = ident_of_fd(self.fp)
'''
new = '''    def _open_path(self, start: int = 0) -> None:
        self.close()
        self.fp = _open_shared_delete(self.path)
        if start:
            self.fp.seek(start)
        self.ident = ident_of_fd(self.fp)
'''
assert old in src, "FollowReader._open_path"
src = src.replace(old, new, 1)

# StuckFdReader.poll open site
old = '''            if self.fp is None:
                if not self.path.is_file():
                    return []
                self.fp = open(self.path, "rb")
'''
new = '''            if self.fp is None:
                if not self.path.is_file():
                    return []
                self.fp = _open_shared_delete(self.path)
'''
assert old in src, "StuckFdReader open"
src = src.replace(old, new, 1)

# RecountOnRotateReader._open_path
old = '''    def _open_path(self) -> None:
        self.close()
        self.fp = open(self.path, "rb")
        self.ident = ident_of_fd(self.fp)
'''
new = '''    def _open_path(self) -> None:
        self.close()
        self.fp = _open_shared_delete(self.path)
        self.ident = ident_of_fd(self.fp)
'''
assert old in src, "RecountOnRotateReader._open_path"
src = src.replace(old, new, 1)

p = P.write_text(src, encoding="utf-8", newline="\n")
print("patched", P)
