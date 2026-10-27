"""A tree containing NUL still enumerates completely; relpath returns NUL (IMP-0467)."""
from __future__ import annotations

import ctypes
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

import windows_safe_path as wsp  # noqa: E402

CREATE_ALWAYS = 2
GENERIC_WRITE = 0x40000000


def _win_prefix(path: Path) -> str:
    return "\\\\" + "?\\" + str(path) if False else chr(92) * 2 + "?" + chr(92) + str(path)


def _create_file(path: Path, body: bytes) -> bool:
    h = ctypes.windll.kernel32.CreateFileW(
        _win_prefix(path), GENERIC_WRITE, 0, None, CREATE_ALWAYS, 0, None)
    if h in (-1, 0xFFFFFFFFFFFFFFFF):
        return False
    import ctypes as c2
    written = c2.c_ulong(0)
    ctypes.windll.kernel32.WriteFile(h, body, len(body), c2.byref(written), None)
    ctypes.windll.kernel32.CloseHandle(h)
    return True


def build_tree(root: Path, with_nul: bool) -> Path:
    base = root / ("with" if with_nul else "without")
    (base / "keep").mkdir(parents=True)
    (base / "nested").mkdir()
    (base / "keep" / "a.txt").write_bytes(b"a\n")
    (base / "keep" / "b.txt").write_bytes(b"b\n")
    (base / "nested" / "c.txt").write_bytes(b"c\n")
    if with_nul:
        ok = _create_file(base / "NUL", b"reserved-nul-body\n")
        assert ok, "NUL fixture creation failed via extended-length prefix"
    return base


def _win_delete(path: Path) -> None:
    ctypes.windll.kernel32.DeleteFileW(_win_prefix(path))


def main() -> int:
    results = {}
    root = HERE / "fixtures-tmp"
    import shutil
    try:
        shutil.rmtree(root)
    except OSError:
        for nul in root.rglob("NUL"):
            _win_delete(nul)
        shutil.rmtree(root, ignore_errors=True)
    try:
        without = build_tree(root, with_nul=False)
        res_wo = wsp.walk_tree(str(without))
        files_wo = sorted(e.relpath for e in res_wo.entries if not e.is_dir)
        assert len(files_wo) == 3, files_wo
        assert all(e.reserved_stem is None for e in res_wo.entries)
        assert wsp.posix_file_count(str(without)) == 3

        with_nul = build_tree(root, with_nul=True)
        res_w = wsp.walk_tree(str(with_nul))
        files_w = sorted(e.relpath for e in res_w.entries if not e.is_dir)
        reserved = [e.relpath for e in res_w.entries if e.reserved_stem]
        assert "NUL" in files_w, files_w
        assert len(files_w) == 4, files_w
        assert reserved == ["NUL"], reserved

        swallow = wsp.swallowing_walk_count(str(with_nul))
        assert swallow == 0, "defect replica must swallow to zero"

        nul_path = str(with_nul / "NUL")
        safe = wsp.safe_relpath(nul_path, str(with_nul))
        assert safe == "NUL", safe
        try:
            wsp.naive_windows_relpath(nul_path, str(with_nul))
            naive_raises = False
        except ValueError:
            naive_raises = True
        assert naive_raises, "naive relpath must raise on reserved names"

    finally:
        for nul in root.rglob("NUL"):
            _win_delete(nul)
        shutil.rmtree(root, ignore_errors=True)

    print(json.dumps({
        "probe": "probe1-reserved-enum",
        "unit_id": "IMP-0467",
        "files_without_reserved": len(files_wo),
        "files_with_reserved": len(files_w),
        "delta": len(files_w) - len(files_wo),
        "reserved_stems": reserved,
        "swallowing_count_on_reserved_tree": swallow,
        "library_does_not_return_zero": len(files_w) > 0,
        "safe_relpath_for_NUL": safe,
        "naive_windows_relpath_raises": naive_raises,
        "sentinel": "SENTINEL:IMP-0467:PATH-LIBRARY-WINDOWS-SAFE",
    }, indent=2))
    print("SUCCESS:IMP-0467-probe1 NUL tree enumerates completely; safe relpath = NUL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
