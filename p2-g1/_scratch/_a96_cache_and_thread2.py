"""Shard2-w1 fix 2026-10-24: AUD-0096 cache invalidation + threaded collect.

Defect introduced by the walk memoization: leak_identity_control measures
the empty sandbox BEFORE copy_user_skills_into mutates it, so the cached
empty listings poisoned the post-copy measure (leaked_user_count=0,
identity control falsely red). Fix: copy_user_skills_into purges the walk
cache after copying (single 'return copied' in the file is this function's).

Plus a pure-perf cut: collect_from_roots walks its ~22 roots serially
(~65s here); roots are independent and the result is key-deduped + sorted,
so a small thread pool changes no semantics, only wall time.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0096/loadset.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a96v3.pyc")

OLD_COLLECT = """def collect_from_roots(
    base: Path, roots: tuple[str, ...], *, scope: str
) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for rel in roots:
        loc = base / rel
        for path in _walk_files(loc):
            for item in classify_file(path, scope=scope, root=base):
                found[item["key"]] = item
    return [found[k] for k in sorted(found)]"""

NEW_COLLECT = """def collect_from_roots(
    base: Path, roots: tuple[str, ...], *, scope: str
) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}

    def _collect_root(rel: str) -> dict[str, dict[str, str]]:
        # shard2-w1 2026-10-24: roots are independent; the caller dedupes by
        # key and returns sorted, so walking roots on a small thread pool is
        # order-safe (os.walk is I/O-bound and releases the GIL).
        loc = base / rel
        out: dict[str, dict[str, str]] = {}
        for path in _walk_files(loc):
            for item in classify_file(path, scope=scope, root=base):
                out[item["key"]] = item
        return out

    if len(roots) >= 4:
        try:
            import os as _os
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=min(8, (_os.cpu_count() or 2))) as pool:
                for part in pool.map(_collect_root, roots):
                    found.update(part)
        except Exception:
            found = {}
            for rel in roots:
                found.update(_collect_root(rel))
    else:
        for rel in roots:
            found.update(_collect_root(rel))
    return [found[k] for k in sorted(found)]"""

OLD_TAIL = "                        skipped += 1\n    return copied"

NEW_TAIL = """            copied += 1
    # shard2-w1 2026-10-24: the destination home just mutated. The walk
    # memoization must not serve the pre-copy listings to the post-copy
    # measure (measured defect: leaked_user_count=0, leak identity falsely
    # red). Purge the cache; the sandbox re-walk is cheap.
    _WALK_CACHE.clear()
    return copied"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_collect_root" in text:
        print("already-patched")
        return 0
    assert text.count("    return copied") == 1, "return copied not unique"
    assert OLD_COLLECT in text, "anchor: collect_from_roots"
    assert OLD_TAIL in text, "anchor: copy tail"
    text = text.replace(OLD_COLLECT, NEW_COLLECT, 1)
    text = text.replace(OLD_TAIL, NEW_TAIL, 1)
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
