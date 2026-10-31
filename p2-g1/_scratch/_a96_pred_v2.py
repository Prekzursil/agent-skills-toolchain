"""Shard2-w1 refinement 2026-10-24: AUD-0096 copy predicate v2 + threaded copy.

v1 of _copy_relevant matched /hooks/ and /rules/ anywhere in the relative
path, which over-copies plugin-cache files that _is_harness_kind_dir would
reject. The exact keys-preserving predicate is classify_file itself: a file
contributes a user_key iff classify_file(path, scope='user', root=home)
returns at least one item. This patch:
  1. rewrites _copy_relevant to delegate to classify_file (fast name-set
     path first, classify_file fallback), and
  2. copies through a small thread pool (copy2 is I/O-bound and releases
     the GIL), preserving the copied-set exactly.
"""
from __future__ import annotations

import py_compile
from pathlib import Path

P = Path(r"C:/Users/Prekzursil/p2-g1/command-center/p2-wave/probes/AUD-0096/loadset.py")
PYC = Path(r"C:/Users/Prekzursil/p2-g1/_scratch/_a96v2.pyc")

OLD_PRED = '''def _copy_relevant(rel_path: Path) -> bool:
    """True only for files that can contribute a user_key
    (shard2-w1 2026-10-24: copy only key-bearing files; plugin
    cache internals contribute zero keys and cannot be copied
    reliably on Windows cache dirs)."""
    name = rel_path.name
    if name in {"SKILL.md", "plugin.json", "mcp.json", ".mcp.json",
                "claude_desktop_config.json", "settings.json",
                ".claude.json", "hooks.json"}:
        return True
    lower = rel_path.as_posix().lower()
    if "/hooks/" in "/" + lower or "/rules/" in "/" + lower:
        return True
    return False'''

NEW_PRED = '''_KEY_BEARING_NAMES = {
    "SKILL.md", "plugin.json", "mcp.json", ".mcp.json",
    "claude_desktop_config.json", "settings.json", ".claude.json",
    "hooks.json",
}


def _copy_relevant(src_home: Path, path: Path) -> bool:
    """True iff the file can contribute a user_key (shard2-w1 2026-10-24).

    Exact predicate: classify_file returns at least one item for it. The
    name fast-path avoids re-classifying the common skill manifests; the
    fallback delegates to classify_file itself, so the copied set preserves
    user_keys by construction (v1 matched /hooks/ and /rules/ anywhere,
    which over-copied plugin-cache files _is_harness_kind_dir rejects)."""
    if path.name in _KEY_BEARING_NAMES:
        return True
    return bool(classify_file(path, scope="user", root=src_home))'''

OLD_LOOP = """        for path in _walk_files(src):
            if _is_secret_name(path.name):            continue
            rel_path = path.relative_to(src_home)
            if not _copy_relevant(rel_path):
                skipped += 1
                continue
            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(path, dest)
            except OSError:
                skipped += 1
                continue
            copied += 1
    return copied"""

NEW_LOOP = """        rels = []
        for path in _walk_files(src):
            if _is_secret_name(path.name):
                continue
            rel_path = path.relative_to(src_home)
            if not _copy_relevant(src_home, path):
                skipped += 1
                continue
            rels.append((path, rel_path))
        if rels:
            # shard2-w1 2026-10-24: copy2 is I/O-bound and releases the GIL;
            # a small pool cuts the ~2000-file copy without changing the
            # copied set, the order of key production, or any assertion.
            from concurrent.futures import ThreadPoolExecutor

            def _cp(job):
                path, rel_path = job
                dest = dest_home / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(path, dest)
                    return True
                except OSError:
                    return False

            with ThreadPoolExecutor(max_workers=min(8, (os.cpu_count() or 2))) as pool:
                for ok in pool.map(_cp, rels):
                    if ok:
                        copied += 1
                    else:
                        skipped += 1
    return copied"""


def main() -> int:
    text = P.read_text(encoding="utf-8")
    if "_KEY_BEARING_NAMES" in text:
        print("already-patched")
        return 0
    assert OLD_PRED in text, "anchor: predicate v1"
    assert OLD_LOOP in text, "anchor: copy loop"
    text = text.replace(OLD_PRED, NEW_PRED, 1)
    text = text.replace(OLD_LOOP, NEW_LOOP, 1)
    P.write_bytes(text.encode("utf-8"))
    py_compile.compile(str(P), doraise=True, cfile=str(PYC))
    print("PATCHED + COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
