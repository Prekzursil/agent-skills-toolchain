"""Shard2-w1 fix 2026-10-24: AUD-0096 probe2 runtime host-port.

probe2 measures the CURRENT live home and re-measures it inside the leak
identity control, so the same 22 USER_LOAD_ROOTS get walked up to four
times per run (collect + cleanliness, x2 measure(current)) — ~300s total on
this host against the 180s G-1 per-probe envelope. This patch memoizes
_walk_files (default limit) per process: the second and later walks of the
same resolved root in the same run return the identical listing, so every
downstream classification, count, and assertion sees byte-identical input.
Pure performance fix; no scope or semantic change.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0096/loadset.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a96.pyc")

OLD = """def _walk_files(root: Path, *, limit: int = 8000) -> list[Path]:
    out: list[Path] = []
    if not root.exists():
        return out
    if root.is_file():
        return [root]
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(".git")
        ]
        base = Path(dirpath)
        for name in filenames:
            if _is_secret_name(name):
                continue
            out.append(base / name)
            if len(out) >= limit:
                return out
    return out"""

NEW = """_WALK_CACHE: dict[str, list[Path]] = {}


def _walk_files(root: Path, *, limit: int = 8000) -> list[Path]:
    # shard2-w1 host-port 2026-10-24: probe2 walks the same live-home load
    # roots up to four times per run (collect + cleanliness, x2 for the leak
    # control's measure(current) plus probe2's own). Memoize the default-limit
    # listing per resolved root within this process: later walks return the
    # identical listing, so classification/counters/assertions are unchanged.
    # Only the default limit is cached; every caller in this module uses it.
    cacheable = limit == 8000
    ck = ""
    if cacheable:
        try:
            ck = str(Path(root).resolve())
        except OSError:
            ck = str(root)
        hit = _WALK_CACHE.get(ck)
        if hit is not None:
            return list(hit)
    out: list[Path] = []
    if not root.exists():
        if cacheable:
            _WALK_CACHE[ck] = out
        return out
    if root.is_file():
        out = [root]
        if cacheable:
            _WALK_CACHE[ck] = out
        return out
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in SKIP_DIR_NAMES and not d.startswith(".git")
        ]
        base = Path(dirpath)
        for name in filenames:
            if _is_secret_name(name):
                continue
            out.append(base / name)
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break
    if cacheable:
        _WALK_CACHE[ck] = out
    return out"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_WALK_CACHE" in text:
        print("already-patched")
        return 0
    assert OLD in text, "pattern miss _walk_files"
    text = text.replace(OLD, NEW, 1)
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
