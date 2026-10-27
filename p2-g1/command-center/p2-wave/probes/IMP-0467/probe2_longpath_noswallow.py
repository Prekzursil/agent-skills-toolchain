"""Long path above 260 round-trips; no silent zero-swallow (IMP-0467)."""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

import windows_safe_path as wsp  # noqa: E402

CREATE_ALWAYS = 2
GENERIC_WRITE = 0x40000000


def _prefix(path: Path) -> str:
    return chr(92) * 2 + "?" + chr(92) + str(path)


def _create(path: Path, body: bytes) -> bool:
    h = ctypes.windll.kernel32.CreateFileW(
        _prefix(path), GENERIC_WRITE, 0, None, CREATE_ALWAYS, 0, None)
    if h in (-1, 0xFFFFFFFFFFFFFFFF):
        return False
    import ctypes as c2
    written = c2.c_ulong(0)
    ctypes.windll.kernel32.WriteFile(h, body, len(body), c2.byref(written), None)
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def _win_delete(path: Path) -> None:
    ctypes.windll.kernel32.DeleteFileW(_prefix(path))


def main() -> int:
    root = HERE / "fixtures-tmp-lp"
    shutil.rmtree(root, ignore_errors=True)
    deep_dir = root / ("d" * 40)
    deep_dir.mkdir(parents=True)
    long_name = "L" * 250
    long_path = deep_dir / long_name
    assert len(str(long_path)) > 260, len(str(long_path))
    body = "long-path-roundtrip\n"
    assert _create(long_path, body.encode("utf-8")), "long-path create failed"

    # the library reads it back through the extended prefix (no swallow)
    read_back = wsp.read_text(_prefix(long_path))
    assert read_back == body, repr(read_back[:40])

    # reserved-tree swallow control: replica zeroes, library walks non-zero
    nul_path = root / "NUL"
    assert _create(nul_path, b"x\n")
    res = wsp.walk_tree(str(root))
    n = sum(1 for e in res.entries if not e.is_dir)
    assert n >= 2, n
    swallow = wsp.swallowing_walk_count(str(root))
    assert swallow == 0, swallow
    assert n != swallow, "library must not swallow reserved/long entries to zero"

    for p in (long_path, nul_path):
        _win_delete(p)
    shutil.rmtree(root, ignore_errors=True)

    print(json.dumps({
        "probe": "probe2-longpath-noswallow",
        "unit_id": "IMP-0467",
        "long_path_chars": len(str(long_path)),
        "long_path_above_260": True,
        "roundtrip_ok": read_back == body,
        "library_walk_count": n,
        "swallowing_replica_count": swallow,
        "library_does_not_swallow": n != swallow,
        "sentinel": "SENTINEL:IMP-0467:PATH-LIBRARY-WINDOWS-SAFE",
    }, indent=2))
    print("SUCCESS:IMP-0467-probe2 260+ char path round-trips; no zero-swallow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
