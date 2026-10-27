#!/usr/bin/env python3
"""Patch AUD-0096 loadset.py: tolerate files vanishing mid-copy."""
from __future__ import annotations

from pathlib import Path

P2 = Path("C:/Users/Prekzursil/p2-g1")
LOADSET = P2 / "command-center/p2-wave/probes/AUD-0096/loadset.py"

OLD = """            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied += 1"""
NEW = """            dest = dest_home / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(path, dest)
            except FileNotFoundError:
                # shard2-resume copy tolerance 2026-10-24: concurrent sessions
                # touch ~/.claude/skills; a file listed by the walk may vanish
                # before the copy. Skip instead of crashing the measurement.
                skipped += 1
                continue
            copied += 1"""
INIT_OLD = "    copied = 0"
INIT_NEW = "    copied = 0\n    skipped = 0"
RET_OLD = "    return copied"
RET_NEW = "    return copied"


def main() -> int:
    text = LOADSET.read_text(encoding="utf-8")
    if "shard2-resume copy tolerance" in text:
        print("already patched")
        return 0
    if OLD not in text:
        print("PATTERN-MISS: copy block not found")
        return 1
    text = text.replace(OLD, NEW, 1)
    n_inits = text.count(INIT_OLD)
    print("copied=0 occurrences:", n_inits)
    text = text.replace(INIT_OLD, INIT_NEW, 1)
    LOADSET.write_text(text, encoding="utf-8", newline="\n")
    print("patched; verifying compile")
    import py_compile
    py_compile.compile(str(LOADSET), doraise=True, cfile=str(P2 / "_scratch/_ls.pyc"))
    print("COMPILE-OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
